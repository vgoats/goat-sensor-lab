package com.vgoats.sensorlab.data

import android.content.Context
import android.os.SystemClock
import com.vgoats.sensorlab.BuildConfig
import com.vgoats.sensorlab.domain.BehaviorLabels
import com.vgoats.sensorlab.domain.SensorFrame
import com.vgoats.sensorlab.domain.SensorSourceType
import com.vgoats.sensorlab.domain.SessionConfig
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedWriter
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.nio.charset.StandardCharsets
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.UUID

data class SessionSummary(
    val sessionId: String,
    val directory: File,
    val startedAtEpochMs: Long,
    val endedAtEpochMs: Long?,
    val sampleCount: Long,
    val firstSampleMonotonicNs: Long? = null,
    val lastSampleMonotonicNs: Long? = null,
)

internal interface RecorderClock {
    fun wallTimeEpochMs(): Long
    fun monotonicTimeNs(): Long
}

private object AndroidRecorderClock : RecorderClock {
    override fun wallTimeEpochMs(): Long = System.currentTimeMillis()
    override fun monotonicTimeNs(): Long = SystemClock.elapsedRealtimeNanos()
}

private class DurableWriter(file: File) {
    private val output = FileOutputStream(file)
    private val writer: BufferedWriter = BufferedWriter(
        OutputStreamWriter(output, StandardCharsets.UTF_8),
    )

    fun appendLine(value: String) {
        writer.append(value)
        writer.newLine()
        writer.flush()
    }

    fun sync() {
        writer.flush()
        output.fd.sync()
    }

    fun close() {
        writer.close()
    }
}

private data class LabelTransition(
    val effectiveMonotonicNs: Long,
    val labels: BehaviorLabels,
)

class ExperimentRecorder internal constructor(
    private val root: File,
    private val clock: RecorderClock,
    private val appVersion: String,
) {
    constructor(context: Context) : this(
        root = File(context.filesDir, "experiments"),
        clock = AndroidRecorderClock,
        appVersion = BuildConfig.VERSION_NAME,
    )

    private var sampleWriter: DurableWriter? = null
    private var eventWriter: DurableWriter? = null
    private var config: SessionConfig? = null
    private var labels = BehaviorLabels()
    private val labelTimeline = mutableListOf<LabelTransition>()
    private var currentSummary: SessionSummary? = null
    private var lastCheckpointMonotonicNs = Long.MIN_VALUE
    private var activeDeviceId: String? = null
    private var lastSequence: Long? = null

    val activeSession: SessionSummary?
        @Synchronized get() = currentSummary

    @Synchronized
    fun start(sessionConfig: SessionConfig): SessionSummary {
        check(currentSummary == null) { "A recording session is already active" }
        check(root.isDirectory || root.mkdirs()) { "Unable to create experiment storage" }
        val startedAt = clock.wallTimeEpochMs()
        val sessionId =
            "${FILE_TIME_FORMAT.format(Instant.ofEpochMilli(startedAt))}_${UUID.randomUUID().toString().take(8)}"
        val directory = File(root, sessionId)
        check(directory.mkdir()) { "Unable to create session directory" }
        val summary = SessionSummary(sessionId, directory, startedAt, null, 0)

        try {
            config = sessionConfig
            labels = BehaviorLabels()
            labelTimeline.clear()
            currentSummary = summary
            lastCheckpointMonotonicNs = Long.MIN_VALUE
            activeDeviceId = null
            lastSequence = null
            writeMetadata(summary, RECORDING)

            sampleWriter = DurableWriter(File(directory, SAMPLES_FILE)).also {
                it.appendLine(SAMPLE_HEADER)
                it.sync()
            }
            eventWriter = DurableWriter(File(directory, EVENTS_FILE)).also {
                it.appendLine(EVENT_HEADER)
                it.sync()
            }
            val startMonotonicNs = clock.monotonicTimeNs()
            writeLabelEvent("session_start", labels, startedAt, startMonotonicNs)
            labelTimeline += LabelTransition(startMonotonicNs, labels)
            return summary
        } catch (error: Throwable) {
            closeWritersQuietly()
            resetActiveState()
            directory.deleteRecursively()
            throw error
        }
    }

    @Synchronized
    fun append(frame: SensorFrame): Long {
        val summary = checkNotNull(currentSummary) { "No active session" }
        val sessionConfig = checkNotNull(config)
        check(frame.source == sessionConfig.source) {
            "Frame source ${frame.source} does not match session source ${sessionConfig.source}"
        }
        val priorDevice = activeDeviceId
        check(priorDevice == null || priorDevice == frame.deviceId) {
            "Frame device ${frame.deviceId} does not match active device $priorDevice"
        }
        val priorSequence = lastSequence
        check(priorSequence == null || frame.sequence > priorSequence) {
            "Frame sequence ${frame.sequence} is not strictly after $priorSequence"
        }
        val priorTime = summary.lastSampleMonotonicNs
        check(priorTime == null || frame.monotonicTimeNs > priorTime) {
            "Frame monotonic time ${frame.monotonicTimeNs} is not strictly after $priorTime"
        }
        val frameLabels = labelsAt(frame.monotonicTimeNs)
        val row = Csv.row(
            frame.schemaVersion,
            summary.sessionId,
            sessionConfig.animalId,
            sessionConfig.species.name,
            sessionConfig.placement.name,
            frame.source.name,
            frame.deviceId,
            frame.sequence,
            frame.wallTimeEpochMs,
            frame.monotonicTimeNs,
            frame.sourceUptimeMs,
            frame.gyroscopeTimeNs,
            frame.accelerationXMs2,
            frame.accelerationYMs2,
            frame.accelerationZMs2,
            frame.gyroscopeXRadS,
            frame.gyroscopeYRadS,
            frame.gyroscopeZRadS,
            frame.temperatureC,
            frame.batteryPercent,
            frame.rssiDbm,
            frameLabels.ingestive.name,
            frameLabels.postureActivity.name,
            frameLabels.welfare.name,
            frameLabels.invalidData,
        )
        checkNotNull(sampleWriter).appendLine(row)
        val updated = summary.copy(
            sampleCount = summary.sampleCount + 1,
            firstSampleMonotonicNs = summary.firstSampleMonotonicNs
                ?.let { minOf(it, frame.monotonicTimeNs) }
                ?: frame.monotonicTimeNs,
            lastSampleMonotonicNs = summary.lastSampleMonotonicNs
                ?.let { maxOf(it, frame.monotonicTimeNs) }
                ?: frame.monotonicTimeNs,
        )
        currentSummary = updated
        activeDeviceId = frame.deviceId
        lastSequence = frame.sequence

        val nowMonotonicNs = clock.monotonicTimeNs()
        if (
            updated.sampleCount == 1L ||
            lastCheckpointMonotonicNs == Long.MIN_VALUE ||
            nowMonotonicNs - lastCheckpointMonotonicNs >= CHECKPOINT_INTERVAL_NS
        ) {
            checkNotNull(sampleWriter).sync()
            writeMetadata(updated, RECORDING)
            lastCheckpointMonotonicNs = nowMonotonicNs
        }
        return updated.sampleCount
    }

    @Synchronized
    fun updateLabels(newLabels: BehaviorLabels) {
        if (labels == newLabels || currentSummary == null) return
        val effectiveMonotonicNs = clock.monotonicTimeNs()
        writeLabelEvent(
            eventType = "label_change",
            eventLabels = newLabels,
            wallTimeEpochMs = clock.wallTimeEpochMs(),
            monotonicTimeNs = effectiveMonotonicNs,
        )
        labels = newLabels
        labelTimeline += LabelTransition(effectiveMonotonicNs, newLabels)
    }

    @Synchronized
    fun updateSourceDeviceMetadata(metadata: Map<String, String>) {
        val summary = currentSummary ?: return
        val existing = checkNotNull(config)
        val merged = existing.sourceDeviceMetadata.toMutableMap()
        val droppedSamples = metadata["device_dropped_samples"]
        if (droppedSamples != null) {
            val priorDroppedSamples = merged["device_dropped_samples"]
            merged.putIfAbsent(
                "device_dropped_samples_start",
                priorDroppedSamples ?: droppedSamples,
            )
            merged["device_dropped_samples_end"] = droppedSamples
        }
        merged.putAll(metadata - "device_dropped_samples")
        merged.remove("device_dropped_samples")
        if (existing.sourceDeviceMetadata == merged) return
        config = existing.copy(sourceDeviceMetadata = merged.toSortedMap())
        writeMetadata(summary, RECORDING)
    }

    @Synchronized
    fun stop(): SessionSummary? {
        val summary = currentSummary ?: return null
        try {
            writeLabelEvent(
                eventType = "session_stop",
                eventLabels = labels,
                wallTimeEpochMs = clock.wallTimeEpochMs(),
                monotonicTimeNs = clock.monotonicTimeNs(),
            )
            checkNotNull(sampleWriter).sync()
            checkNotNull(eventWriter).sync()
            val completed = summary.copy(endedAtEpochMs = clock.wallTimeEpochMs())
            writeMetadata(completed, COMPLETED)
            return completed
        } finally {
            closeWritersQuietly()
            resetActiveState()
        }
    }

    /** Repair interrupted sessions to canonical CSV prefixes and mark only valid ones exportable. */
    @Synchronized
    fun recoverIncompleteSessions(): List<SessionSummary> {
        check(currentSummary == null) { "Cannot recover sessions while recording" }
        val recoveredAt = clock.wallTimeEpochMs()
        return root.listFiles()
            .orEmpty()
            .filter(File::isDirectory)
            .mapNotNull { recoverDirectory(it, recoveredAt) }
            .sortedBy { it.startedAtEpochMs }
    }

    /** Return the newest session that passes the same structural gate used by export. */
    @Synchronized
    fun latestExportableSession(): SessionSummary? = root.listFiles()
        .orEmpty()
        .filter(File::isDirectory)
        .mapNotNull { directory ->
            val validation = SessionIntegrity.validateForExport(directory)
            if (!validation.valid) return@mapNotNull null
            val metadata = checkNotNull(validation.metadata)
            SessionSummary(
                sessionId = metadata.optString("session_id", directory.name),
                directory = directory,
                startedAtEpochMs = metadata.optLong("started_at_epoch_ms", directory.lastModified()),
                endedAtEpochMs = metadata.nullableLong("ended_at_epoch_ms"),
                sampleCount = validation.sampleCount,
                firstSampleMonotonicNs = metadata.nullableLong("first_sample_monotonic_ns"),
                lastSampleMonotonicNs = metadata.nullableLong("last_sample_monotonic_ns"),
            )
        }
        .maxByOrNull { it.startedAtEpochMs }

    private fun recoverDirectory(directory: File, recoveredAt: Long): SessionSummary? {
        val metadataFile = File(directory, METADATA_FILE)
        val originalMetadata = readJson(metadataFile)
        val state = originalMetadata?.optString("recording_state")
        val ended = originalMetadata?.nullableLong("ended_at_epoch_ms")
        if (state == COMPLETED || (state.isNullOrBlank() && ended != null)) return null

        if (state == INCOMPLETE_RECOVERED) {
            val priorValidation = SessionIntegrity.validateForExport(directory)
            if (priorValidation.valid) {
                return summaryFromValidation(directory, priorValidation)
            }
            if (originalMetadata.optBoolean("exportable", true) == false) return null
        }

        val samples = Csv.recoverCanonical(
            file = File(directory, SAMPLES_FILE),
            expectedHeader = SessionIntegrity.sampleHeader,
            identityColumnIndex = SessionIntegrity.SAMPLE_SESSION_ID_INDEX,
            recoveryEpochMs = recoveredAt,
        )
        val events = Csv.recoverCanonical(
            file = File(directory, EVENTS_FILE),
            expectedHeader = SessionIntegrity.eventHeader,
            identityColumnIndex = SessionIntegrity.EVENT_SESSION_ID_INDEX,
            recoveryEpochMs = recoveredAt,
        )
        val issues = mutableListOf<String>()
        if (!samples.sourceHeaderValid) issues += samples.issue ?: "samples.csv header was invalid"
        if (!events.sourceHeaderValid) issues += events.issue ?: "events.csv header was invalid"
        if (samples.dataRecordCount <= 0) issues += "samples.csv contains no recoverable data"
        if (!samples.identityConsistent || samples.identityValue.isNullOrBlank()) {
            issues += "samples.csv session IDs are missing or inconsistent"
        }
        if (!events.identityConsistent ||
            (events.dataRecordCount > 0 && events.identityValue != samples.identityValue)
        ) {
            issues += "events.csv session IDs are inconsistent with samples.csv"
        }

        val firstSample = samples.firstDataRecord
        val lastSample = samples.lastDataRecord
        val sessionId = samples.identityValue?.takeIf { samples.identityConsistent && it.isNotBlank() }
            ?: originalMetadata?.optString("session_id")?.takeIf(String::isNotBlank)
            ?: directory.name
        if (firstSample != null) {
            REQUIRED_SAMPLE_PROVENANCE_COLUMNS.forEach { index ->
                if (firstSample[index].isBlank()) {
                    issues += "samples.csv has missing ${SessionIntegrity.sampleHeader[index]} provenance"
                }
            }
        }
        if (originalMetadata != null &&
            originalMetadata.optString("session_id").isNotBlank() &&
            originalMetadata.optString("session_id") != samples.identityValue
        ) {
            issues += "session.json and samples.csv session IDs differ"
        }

        val metadata = if (originalMetadata == null) {
            if (metadataFile.exists()) Csv.quarantineCopy(metadataFile, recoveredAt)
            reconstructedMetadata(
                directory = directory,
                sessionId = sessionId,
                firstSample = firstSample,
                lastSample = lastSample,
                sampleCount = samples.dataRecordCount,
                recoveredAt = recoveredAt,
            )
        } else {
            originalMetadata
        }
        val firstMonotonic = firstSample?.getOrNull(SAMPLE_MONOTONIC_INDEX)?.toLongOrNull()
        val lastMonotonic = lastSample?.getOrNull(SAMPLE_MONOTONIC_INDEX)?.toLongOrNull()
        if (firstSample != null && (firstMonotonic == null || lastMonotonic == null)) {
            issues += "samples.csv monotonic timestamps are not integers"
        }
        val exportable = issues.isEmpty()
        metadata
            .put("session_id", sessionId)
            .put("recording_state", INCOMPLETE_RECOVERED)
            .put("sample_count", samples.dataRecordCount)
            .putNullable("first_sample_monotonic_ns", firstMonotonic)
            .putNullable("last_sample_monotonic_ns", lastMonotonic)
            .put("recovered_at_epoch_ms", recoveredAt)
            .put("exportable", exportable)
            .put(
                "csv_recovery",
                JSONObject()
                    .put("samples_repaired", samples.repaired)
                    .put("events_repaired", events.repaired)
                    .put("samples_retained_records", samples.dataRecordCount)
                    .put("events_retained_records", events.dataRecordCount),
            )
        if (exportable) {
            metadata.remove("non_exportable_reason")
        } else {
            metadata.put("non_exportable_reason", issues.distinct().joinToString("; "))
        }
        atomicWriteJson(metadataFile, metadata)

        val validation = SessionIntegrity.validateForExport(directory)
        if (!validation.valid) {
            if (exportable) {
                metadata
                    .put("exportable", false)
                    .put(
                        "non_exportable_reason",
                        validation.reason ?: "Recovered session failed export validation",
                    )
                atomicWriteJson(metadataFile, metadata)
            }
            return null
        }
        return summaryFromValidation(directory, validation)
    }

    private fun reconstructedMetadata(
        directory: File,
        sessionId: String,
        firstSample: List<String>?,
        lastSample: List<String>?,
        sampleCount: Long,
        recoveredAt: Long,
    ): JSONObject {
        val startedAt = firstSample?.getOrNull(SAMPLE_WALL_TIME_INDEX)?.toLongOrNull()
            ?: directory.lastModified()
        val sourceMetadata = JSONObject()
        firstSample?.getOrNull(SAMPLE_DEVICE_ID_INDEX)?.takeIf(String::isNotBlank)?.let {
            sourceMetadata.put("observed_device_id", it)
        }
        return JSONObject()
            .put("schema_version", 1)
            .put("session_id", sessionId)
            .put("metadata_origin", "RECONSTRUCTED_FROM_CANONICAL_SAMPLES")
            .put("recovery_missing_fields", JSONArray(RECONSTRUCTED_MISSING_FIELDS))
            .putNullable("animal_id", firstSample?.getOrNull(SAMPLE_ANIMAL_ID_INDEX))
            .putNullable("species", firstSample?.getOrNull(SAMPLE_SPECIES_INDEX))
            .putNullable("placement", firstSample?.getOrNull(SAMPLE_PLACEMENT_INDEX))
            .putNullable("source", firstSample?.getOrNull(SAMPLE_SOURCE_INDEX))
            .put("source_device_metadata", sourceMetadata)
            .putNullable("expected_device_id", null)
            .putNullable("app_version", null)
            .putNullable("ble_protocol_version", null)
            .putNullable("observed_firmware_version", null)
            .putNullable("accelerometer_range_g", null)
            .putNullable("gyroscope_range_dps", null)
            .putNullable("requested_sample_rate_hz", null)
            .putNullable("achieved_sample_rate_hz", null)
            .putNullable("annotator_id", null)
            .putNullable("shed_id", null)
            .putNullable("camera_ids", null)
            .putNullable("notes", null)
            .put("started_at_epoch_ms", startedAt)
            .putNullable("ended_at_epoch_ms", null)
            .put("sample_count", sampleCount)
            .putNullable(
                "first_sample_monotonic_ns",
                firstSample?.getOrNull(SAMPLE_MONOTONIC_INDEX)?.toLongOrNull(),
            )
            .putNullable(
                "last_sample_monotonic_ns",
                lastSample?.getOrNull(SAMPLE_MONOTONIC_INDEX)?.toLongOrNull(),
            )
            .put("checkpointed_at_epoch_ms", recoveredAt)
    }

    private fun summaryFromValidation(
        directory: File,
        validation: ExportValidation,
    ): SessionSummary {
        val metadata = checkNotNull(validation.metadata)
        return SessionSummary(
            sessionId = metadata.getString("session_id"),
            directory = directory,
            startedAtEpochMs = metadata.optLong("started_at_epoch_ms", directory.lastModified()),
            endedAtEpochMs = metadata.nullableLong("ended_at_epoch_ms"),
            sampleCount = validation.sampleCount,
            firstSampleMonotonicNs = metadata.nullableLong("first_sample_monotonic_ns"),
            lastSampleMonotonicNs = metadata.nullableLong("last_sample_monotonic_ns"),
        )
    }

    private fun labelsAt(monotonicTimeNs: Long): BehaviorLabels {
        var low = 0
        var high = labelTimeline.lastIndex
        var match: BehaviorLabels? = null
        while (low <= high) {
            val middle = (low + high).ushr(1)
            val transition = labelTimeline[middle]
            if (transition.effectiveMonotonicNs <= monotonicTimeNs) {
                match = transition.labels
                low = middle + 1
            } else {
                high = middle - 1
            }
        }
        return match ?: BehaviorLabels()
    }

    private fun writeLabelEvent(
        eventType: String,
        eventLabels: BehaviorLabels,
        wallTimeEpochMs: Long,
        monotonicTimeNs: Long,
    ) {
        checkNotNull(eventWriter).apply {
            appendLine(
                Csv.row(
                    wallTimeEpochMs,
                    monotonicTimeNs,
                    checkNotNull(currentSummary).sessionId,
                    eventType,
                    eventLabels.ingestive.name,
                    eventLabels.postureActivity.name,
                    eventLabels.welfare.name,
                    eventLabels.invalidData,
                ),
            )
            sync()
        }
    }

    private fun writeMetadata(summary: SessionSummary, recordingState: String) {
        val sessionConfig = checkNotNull(config)
        val metadata = JSONObject()
            .put("schema_version", 1)
            .put("session_id", summary.sessionId)
            .put("recording_state", recordingState)
            .put("animal_id", sessionConfig.animalId)
            .put("species", sessionConfig.species.name)
            .put("placement", sessionConfig.placement.name)
            .put("source", sessionConfig.source.name)
            .putNullable("expected_device_id", sessionConfig.expectedDeviceId)
            .put("source_device_metadata", JSONObject(sessionConfig.sourceDeviceMetadata))
            .put("app_version", appVersion)
            .putNullable(
                "ble_protocol_version",
                sessionConfig.sourceDeviceMetadata["protocol_version"]?.toIntOrNull(),
            )
            .putNullable(
                "observed_firmware_version",
                sessionConfig.sourceDeviceMetadata["firmware_version"],
            )
            .putNullable(
                "accelerometer_range_g",
                sessionConfig.sourceDeviceMetadata["accelerometer_range_g"]?.toIntOrNull(),
            )
            .putNullable(
                "gyroscope_range_dps",
                sessionConfig.sourceDeviceMetadata["gyroscope_range_dps"]?.toIntOrNull(),
            )
            .put("requested_sample_rate_hz", sessionConfig.sampleRateHz)
            .putNullable("achieved_sample_rate_hz", summary.achievedSampleRateHz())
            .put("annotator_id", sessionConfig.annotatorId)
            .put("shed_id", sessionConfig.shedId)
            .put("camera_ids", sessionConfig.cameraIds)
            .put("notes", sessionConfig.notes)
            .put("started_at_epoch_ms", summary.startedAtEpochMs)
            .putNullable("ended_at_epoch_ms", summary.endedAtEpochMs)
            .put("sample_count", summary.sampleCount)
            .putNullable("first_sample_monotonic_ns", summary.firstSampleMonotonicNs)
            .putNullable("last_sample_monotonic_ns", summary.lastSampleMonotonicNs)
            .put("checkpointed_at_epoch_ms", clock.wallTimeEpochMs())
        atomicWriteJson(File(summary.directory, METADATA_FILE), metadata)
    }

    private fun closeWritersQuietly() {
        runCatching { sampleWriter?.close() }
        runCatching { eventWriter?.close() }
        sampleWriter = null
        eventWriter = null
    }

    private fun resetActiveState() {
        config = null
        labels = BehaviorLabels()
        labelTimeline.clear()
        currentSummary = null
        lastCheckpointMonotonicNs = Long.MIN_VALUE
        activeDeviceId = null
        lastSequence = null
    }

    private fun readJson(file: File): JSONObject? = runCatching {
        JSONObject(file.readText(StandardCharsets.UTF_8))
    }.getOrNull()

    private fun atomicWriteJson(file: File, value: JSONObject) {
        val temporary = File(file.parentFile, ".${file.name}.tmp")
        val output = FileOutputStream(temporary)
        try {
            val writer = BufferedWriter(OutputStreamWriter(output, StandardCharsets.UTF_8))
            writer.write(value.toString(2))
            writer.newLine()
            writer.flush()
            output.fd.sync()
        } finally {
            output.close()
        }
        try {
            Files.move(
                temporary.toPath(),
                file.toPath(),
                StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING,
            )
        } catch (_: AtomicMoveNotSupportedException) {
            Files.move(
                temporary.toPath(),
                file.toPath(),
                StandardCopyOption.REPLACE_EXISTING,
            )
        }
    }

    companion object {
        private val FILE_TIME_FORMAT = DateTimeFormatter
            .ofPattern("yyyyMMdd_HHmmss")
            .withZone(ZoneOffset.UTC)
        private const val CHECKPOINT_INTERVAL_NS = 1_000_000_000L
        private const val RECORDING = "RECORDING"
        private const val COMPLETED = SessionIntegrity.COMPLETED
        private const val INCOMPLETE_RECOVERED = SessionIntegrity.INCOMPLETE_RECOVERED
        private const val SAMPLES_FILE = SessionIntegrity.SAMPLES_FILE
        private const val EVENTS_FILE = SessionIntegrity.EVENTS_FILE
        private const val METADATA_FILE = SessionIntegrity.METADATA_FILE
        private const val SAMPLE_HEADER =
            "schema_version,session_id,animal_id,species,placement,source,device_id,sequence," +
                "wall_time_epoch_ms,monotonic_time_ns,source_uptime_ms,gyro_monotonic_time_ns," +
                "acc_x_m_s2,acc_y_m_s2,acc_z_m_s2," +
                "gyro_x_rad_s,gyro_y_rad_s,gyro_z_rad_s,temperature_c,battery_percent,rssi_dbm," +
                "ingestive_behavior,posture_activity,welfare_state,invalid_data"
        private const val EVENT_HEADER =
            "wall_time_epoch_ms,monotonic_time_ns,session_id,event_type," +
                "ingestive_behavior,posture_activity," +
                "welfare_state,invalid_data"

        private const val SAMPLE_ANIMAL_ID_INDEX = 2
        private const val SAMPLE_SPECIES_INDEX = 3
        private const val SAMPLE_PLACEMENT_INDEX = 4
        private const val SAMPLE_SOURCE_INDEX = 5
        private const val SAMPLE_DEVICE_ID_INDEX = 6
        private const val SAMPLE_WALL_TIME_INDEX = 8
        private const val SAMPLE_MONOTONIC_INDEX = 9
        private val REQUIRED_SAMPLE_PROVENANCE_COLUMNS = listOf(
            SessionIntegrity.SAMPLE_SESSION_ID_INDEX,
            SAMPLE_ANIMAL_ID_INDEX,
            SAMPLE_SPECIES_INDEX,
            SAMPLE_PLACEMENT_INDEX,
            SAMPLE_SOURCE_INDEX,
            SAMPLE_DEVICE_ID_INDEX,
        )
        private val RECONSTRUCTED_MISSING_FIELDS = listOf(
            "expected_device_id",
            "app_version",
            "ble_protocol_version",
            "observed_firmware_version",
            "accelerometer_range_g",
            "gyroscope_range_dps",
            "requested_sample_rate_hz",
            "achieved_sample_rate_hz",
            "annotator_id",
            "shed_id",
            "camera_ids",
            "notes",
            "ended_at_epoch_ms",
        )

        init {
            check(SAMPLE_HEADER == SessionIntegrity.sampleHeaderLine) {
                "Recorder and recovery sample headers disagree"
            }
            check(EVENT_HEADER == SessionIntegrity.eventHeaderLine) {
                "Recorder and recovery event headers disagree"
            }
        }
    }
}

private fun JSONObject.putNullable(name: String, value: Any?): JSONObject = put(
    name,
    value ?: JSONObject.NULL,
)

private fun JSONObject.nullableLong(name: String): Long? = when {
    !has(name) || isNull(name) -> null
    else -> optLong(name)
}

internal fun SessionSummary.achievedSampleRateHz(): Double? {
    val first = firstSampleMonotonicNs ?: return null
    val last = lastSampleMonotonicNs ?: return null
    if (sampleCount < 2 || last <= first) return null
    return (sampleCount - 1) * 1_000_000_000.0 / (last - first)
}
