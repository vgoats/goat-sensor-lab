package com.vgoats.sensorlab.data

import org.json.JSONObject
import java.io.File
import java.nio.charset.StandardCharsets
import java.nio.file.Files

internal data class ExportValidation(
    val valid: Boolean,
    val reason: String?,
    val files: List<File> = emptyList(),
    val sampleCount: Long = 0,
    val metadata: JSONObject? = null,
)

internal object SessionIntegrity {
    const val SAMPLES_FILE = "samples.csv"
    const val EVENTS_FILE = "events.csv"
    const val METADATA_FILE = "session.json"

    val sampleHeader: List<String> = listOf(
        "schema_version",
        "session_id",
        "animal_id",
        "species",
        "placement",
        "source",
        "device_id",
        "sequence",
        "wall_time_epoch_ms",
        "monotonic_time_ns",
        "source_uptime_ms",
        "gyro_monotonic_time_ns",
        "acc_x_m_s2",
        "acc_y_m_s2",
        "acc_z_m_s2",
        "gyro_x_rad_s",
        "gyro_y_rad_s",
        "gyro_z_rad_s",
        "temperature_c",
        "battery_percent",
        "rssi_dbm",
        "ingestive_behavior",
        "posture_activity",
        "welfare_state",
        "invalid_data",
    )
    val eventHeader: List<String> = listOf(
        "wall_time_epoch_ms",
        "monotonic_time_ns",
        "session_id",
        "event_type",
        "ingestive_behavior",
        "posture_activity",
        "welfare_state",
        "invalid_data",
    )

    val sampleHeaderLine: String = Csv.row(*sampleHeader.toTypedArray())
    val eventHeaderLine: String = Csv.row(*eventHeader.toTypedArray())

    fun validateForExport(directory: File): ExportValidation {
        if (!directory.isDirectory || Files.isSymbolicLink(directory.toPath())) {
            return ExportValidation(false, "Session directory is missing or unsafe")
        }
        val metadataFile = File(directory, METADATA_FILE)
        val samplesFile = File(directory, SAMPLES_FILE)
        val eventsFile = File(directory, EVENTS_FILE)
        val requiredFiles = listOf(samplesFile, eventsFile, metadataFile)
        val unsafeFile = requiredFiles.firstOrNull {
            !it.isFile || Files.isSymbolicLink(it.toPath())
        }
        if (unsafeFile != null) {
            return ExportValidation(false, "Missing or unsafe ${unsafeFile.name}")
        }

        val metadata = runCatching {
            JSONObject(metadataFile.readText(StandardCharsets.UTF_8))
        }.getOrElse {
            return ExportValidation(false, "session.json is not valid JSON")
        }
        if (metadata.has("exportable") && !metadata.optBoolean("exportable", false)) {
            return ExportValidation(
                false,
                metadata.optString("non_exportable_reason", "Session recovery marked it non-exportable"),
            )
        }
        val state = metadata.optString("recording_state")
        if (state !in setOf(COMPLETED, INCOMPLETE_RECOVERED)) {
            return ExportValidation(false, "Session state $state is not exportable")
        }

        val samples = Csv.inspectCanonical(samplesFile, sampleHeader, SAMPLE_SESSION_ID_INDEX)
        if (!samples.canonical) {
            return ExportValidation(false, samples.issue ?: "samples.csv is invalid")
        }
        if (samples.dataRecordCount <= 0) {
            return ExportValidation(false, "samples.csv has no data records")
        }
        if (!samples.identityConsistent || samples.identityValue.isNullOrBlank()) {
            return ExportValidation(false, "samples.csv contains inconsistent session IDs")
        }
        val events = Csv.inspectCanonical(eventsFile, eventHeader, EVENT_SESSION_ID_INDEX)
        if (!events.canonical) {
            return ExportValidation(false, events.issue ?: "events.csv is invalid")
        }
        if (!events.identityConsistent ||
            (events.dataRecordCount > 0 && events.identityValue != samples.identityValue)
        ) {
            return ExportValidation(false, "events.csv contains inconsistent session IDs")
        }

        val metadataSessionId = metadata.optString("session_id")
        if (metadataSessionId != samples.identityValue) {
            return ExportValidation(false, "session.json and samples.csv session IDs differ")
        }
        if (metadata.optLong("sample_count", -1L) != samples.dataRecordCount) {
            return ExportValidation(false, "session.json sample_count does not match samples.csv")
        }
        return ExportValidation(
            valid = true,
            reason = null,
            files = listOf(metadataFile, samplesFile, eventsFile),
            sampleCount = samples.dataRecordCount,
            metadata = metadata,
        )
    }

    const val COMPLETED = "COMPLETED"
    const val INCOMPLETE_RECOVERED = "INCOMPLETE_RECOVERED"
    const val SAMPLE_SESSION_ID_INDEX = 1
    const val EVENT_SESSION_ID_INDEX = 2
}
