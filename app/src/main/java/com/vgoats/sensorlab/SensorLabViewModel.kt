package com.vgoats.sensorlab

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import com.vgoats.sensorlab.data.ExperimentRecorder
import com.vgoats.sensorlab.data.SessionExporter
import com.vgoats.sensorlab.data.SessionSummary
import com.vgoats.sensorlab.domain.BehaviorLabels
import com.vgoats.sensorlab.domain.IngestiveBehavior
import com.vgoats.sensorlab.domain.Placement
import com.vgoats.sensorlab.domain.PostureActivity
import com.vgoats.sensorlab.domain.SensorFrame
import com.vgoats.sensorlab.domain.SensorSourceType
import com.vgoats.sensorlab.domain.SessionConfig
import com.vgoats.sensorlab.domain.Species
import com.vgoats.sensorlab.domain.WelfareState
import com.vgoats.sensorlab.sensor.PhoneImuSource
import com.vgoats.sensorlab.sensor.SensorSource
import com.vgoats.sensorlab.sensor.SensorSourceMetadata
import com.vgoats.sensorlab.sensor.XiaoBleSource
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.io.File

data class SensorLabUiState(
    val animalId: String = "PHONE_TEST_001",
    val species: Species = Species.GOAT,
    val placement: Placement = Placement.PHONE_HANDHELD_TEST,
    val sampleRateHz: Int = 25,
    val notes: String = "",
    val annotatorId: String = "",
    val shedId: String = "",
    val cameraIds: String = "",
    val sensorSourceType: SensorSourceType = SensorSourceType.ANDROID_PHONE,
    val boardDeviceId: String = "",
    val sensorDescription: String = "Checking sensors",
    val preparing: Boolean = false,
    val recording: Boolean = false,
    val sessionId: String? = null,
    val startedAtEpochMs: Long? = null,
    val sampleCount: Long = 0,
    val latestFrame: SensorFrame? = null,
    val labels: BehaviorLabels = BehaviorLabels(),
    val message: String? = null,
    val lastSessionName: String? = null,
)

class SensorLabViewModel(application: Application) : AndroidViewModel(application) {
    private val phoneSource = PhoneImuSource(application)
    private val xiaoSource = XiaoBleSource(application)
    private var source: SensorSource = phoneSource
    private val recorder = ExperimentRecorder(application)
    private val recoveredSessions = recorder.recoverIncompleteSessions()
    private val restoredSession = recorder.latestExportableSession()
    private var lastSessionDirectory: File? = restoredSession?.directory

    private val _uiState = MutableStateFlow(
        SensorLabUiState(
            sensorDescription = source.availability.description,
            lastSessionName = restoredSession?.sessionId,
            message = recoveredSessions.lastOrNull { it.sampleCount > 0 }?.let {
                "Recovered interrupted session ${it.sessionId} with ${it.sampleCount} samples; export is available"
            },
        ),
    )
    val uiState: StateFlow<SensorLabUiState> = _uiState.asStateFlow()

    fun setAnimalId(value: String) = updateConfig { copy(animalId = value) }
    fun setSpecies(value: Species) = updateConfig { copy(species = value) }
    fun setPlacement(value: Placement) = updateConfig { copy(placement = value) }
    fun setSampleRate(value: Int) = updateConfig { copy(sampleRateHz = value) }
    fun setNotes(value: String) = updateConfig { copy(notes = value) }
    fun setAnnotatorId(value: String) = updateConfig { copy(annotatorId = value) }
    fun setShedId(value: String) = updateConfig { copy(shedId = value) }
    fun setCameraIds(value: String) = updateConfig { copy(cameraIds = value) }
    fun setBoardDeviceId(value: String) = updateConfig { copy(boardDeviceId = value.uppercase()) }

    fun setSensorSource(value: SensorSourceType) {
        if (_uiState.value.isActive) return
        source.stop()
        source = when (value) {
            SensorSourceType.ANDROID_PHONE -> phoneSource
            SensorSourceType.XIAO_NRF52840_SENSE -> xiaoSource
        }
        _uiState.update {
            it.copy(
                sensorSourceType = value,
                sampleRateHz = when (value) {
                    SensorSourceType.ANDROID_PHONE -> it.sampleRateHz.takeIf { rate -> rate in PHONE_RATES } ?: 25
                    SensorSourceType.XIAO_NRF52840_SENSE -> it.sampleRateHz.takeIf { rate -> rate in XIAO_RATES } ?: 26
                },
                sensorDescription = source.availability.description,
            )
        }
    }

    fun refreshSensorAvailability() {
        _uiState.update { it.copy(sensorDescription = source.availability.description) }
    }

    fun startRecording() {
        val state = _uiState.value
        if (state.isActive) return
        if (state.animalId.isBlank()) {
            _uiState.update { it.copy(message = "Animal ID is required") }
            return
        }
        if (!source.availability.available) {
            _uiState.update { it.copy(message = source.availability.description) }
            return
        }
        if (state.sensorSourceType == SensorSourceType.XIAO_NRF52840_SENSE && state.boardDeviceId.isBlank()) {
            _uiState.update { it.copy(message = "XIAO board ID is required") }
            return
        }

        val summary = runCatching {
            recorder.start(
                SessionConfig(
                    animalId = state.animalId.trim(),
                    species = state.species,
                    placement = state.placement,
                    sampleRateHz = state.sampleRateHz,
                    notes = state.notes.trim(),
                    source = state.sensorSourceType,
                    expectedDeviceId = state.boardDeviceId.trim().ifBlank { null },
                    annotatorId = state.annotatorId.trim(),
                    shedId = state.shedId.trim(),
                    cameraIds = state.cameraIds.trim(),
                    sourceDeviceMetadata = source.verifiedMetadata.asSessionMetadata(),
                ),
            )
        }.getOrElse {
            _uiState.update { current -> current.copy(message = it.message ?: "Unable to start session") }
            return
        }

        _uiState.update {
            it.copy(
                preparing = true,
                recording = false,
                sessionId = summary.sessionId,
                startedAtEpochMs = summary.startedAtEpochMs,
                sampleCount = 0,
                latestFrame = null,
                labels = BehaviorLabels(),
                message = null,
            )
        }
        source.start(
            sampleRateHz = state.sampleRateHz,
            targetDeviceId = state.boardDeviceId.trim().ifBlank { null },
            onFrame = ::onSensorFrame,
            onStatus = { status -> _uiState.update { it.copy(sensorDescription = status) } },
            onReady = ::onSourceReady,
            onError = ::onSourceError,
        ).onFailure { error ->
            onSourceError(error.message ?: "Unable to start sensor source")
        }
    }

    fun stopRecording() {
        if (!_uiState.value.isActive) return
        val metadataFailure = checkpointSourceMetadata()
        source.stop()
        val completion = runCatching { recorder.stop() }
        val completed = completion.getOrNull()
        if (completion.isFailure) runCatching { recorder.recoverIncompleteSessions() }
        completed?.let {
            val saved = it.sampleCount > 0
            if (saved) {
                lastSessionDirectory = it.directory
            } else {
                it.directory.deleteRecursively()
            }
            _uiState.update { state ->
                state.copy(
                    recording = false,
                    preparing = false,
                    sensorDescription = source.availability.description,
                    lastSessionName = it.sessionId.takeIf { saved },
                    message = when {
                        metadataFailure != null && saved ->
                            "Saved ${it.sampleCount} samples; final sensor metadata failed: " +
                                (metadataFailure.message ?: "storage error")
                        metadataFailure != null ->
                            "Session cancelled before data arrived; final sensor metadata failed: " +
                                (metadataFailure.message ?: "storage error")
                        saved -> "Saved ${it.sampleCount} samples"
                        else -> "Session cancelled before data arrived"
                    },
                )
            }
        }
        if (completed == null && completion.isFailure) {
            val recovered = runCatching { recorder.latestExportableSession() }.getOrNull()
            lastSessionDirectory = recovered?.directory
            _uiState.update { state ->
                state.copy(
                    recording = false,
                    preparing = false,
                    sensorDescription = source.availability.description,
                    lastSessionName = recovered?.sessionId,
                    message = "Recording stopped, but finalization failed: " +
                        (completion.exceptionOrNull()?.message ?: "storage error"),
                )
            }
        }
    }

    fun onAppBackgrounded() {
        if (!_uiState.value.isActive) return
        stopRecording()
        _uiState.update { state ->
            if (state.message?.startsWith("Recording stopped, but finalization failed:") == true) {
                state
            } else {
                state.copy(message = "Recording finalized because the app left the foreground")
            }
        }
    }

    fun setIngestive(value: IngestiveBehavior) = updateLabels { copy(ingestive = value) }
    fun setPosture(value: PostureActivity) = updateLabels { copy(postureActivity = value) }
    fun setWelfare(value: WelfareState) = updateLabels { copy(welfare = value) }
    fun setInvalidData(value: Boolean) = updateLabels { copy(invalidData = value) }

    fun shareLastSession(context: Context) {
        val directory = lastSessionDirectory
        if (directory == null) {
            _uiState.update { it.copy(message = "Record a session before exporting") }
        } else {
            SessionExporter.share(context, directory)
        }
    }

    fun exportLastSessionToDownloads(context: Context) {
        val directory = lastSessionDirectory
        if (directory == null) {
            _uiState.update { it.copy(message = "Record a session before exporting") }
            return
        }
        runCatching { SessionExporter.saveToDownloads(context, directory) }
            .onSuccess { path -> _uiState.update { it.copy(message = "Exported $path") } }
            .onFailure { error ->
                _uiState.update {
                    it.copy(message = error.message ?: "Unable to export session")
                }
            }
    }

    fun clearMessage() = _uiState.update { it.copy(message = null) }

    private fun onSensorFrame(frame: SensorFrame) {
        if (!_uiState.value.recording) return
        val count = runCatching { recorder.append(frame) }.getOrElse {
            onSourceError("Unable to write sensor data: ${it.message ?: "storage error"}")
            return
        }
        _uiState.update { it.copy(sampleCount = count, latestFrame = frame) }
    }

    private fun onSourceReady() {
        if (!_uiState.value.preparing || recorder.activeSession == null) return
        val metadataFailure = runCatching {
            recorder.updateSourceDeviceMetadata(source.verifiedMetadata.asSessionMetadata())
        }.exceptionOrNull()
        if (metadataFailure != null) {
            onSourceError("Unable to checkpoint sensor metadata: ${metadataFailure.message}")
            return
        }
        _uiState.update {
            it.copy(
                preparing = false,
                recording = true,
                message = null,
            )
        }
    }

    private fun onSourceError(message: String) {
        if (!_uiState.value.isActive) return
        val metadataFailure = checkpointSourceMetadata()
        source.stop()
        val completion = runCatching { recorder.stop() }
        if (completion.isFailure) runCatching { recorder.recoverIncompleteSessions() }
        val completed = completion.getOrNull()
        val exportable = completed?.takeIf { it.sampleCount > 0 }
            ?: runCatching { recorder.latestExportableSession() }.getOrNull()
                .takeIf { completion.isFailure }
        if (completed != null && completed.sampleCount > 0) {
            lastSessionDirectory = completed.directory
        } else {
            completed?.directory?.deleteRecursively()
            if (exportable != null) lastSessionDirectory = exportable.directory
        }
        _uiState.update {
            it.copy(
                recording = false,
                preparing = false,
                sensorDescription = source.availability.description,
                lastSessionName = exportable?.sessionId,
                message = if (metadataFailure == null) {
                    message
                } else {
                    "$message; final sensor metadata failed: ${metadataFailure.message ?: "storage error"}"
                },
            )
        }
    }

    private fun updateLabels(block: BehaviorLabels.() -> BehaviorLabels) {
        val newLabels = _uiState.value.labels.block()
        val failure = runCatching { recorder.updateLabels(newLabels) }.exceptionOrNull()
        if (failure != null) {
            onSourceError("Unable to write label event: ${failure.message ?: "storage error"}")
            return
        }
        _uiState.update { it.copy(labels = newLabels) }
    }

    private fun updateConfig(block: SensorLabUiState.() -> SensorLabUiState) {
        if (!_uiState.value.isActive) _uiState.update { it.block() }
    }

    override fun onCleared() {
        checkpointSourceMetadata()
        source.stop()
        runCatching { recorder.stop() }
            .onFailure { runCatching { recorder.recoverIncompleteSessions() } }
        super.onCleared()
    }

    companion object {
        val PHONE_RATES = listOf(5, 10, 16, 25, 50)
        val XIAO_RATES = listOf(13, 26)
    }

    private fun checkpointSourceMetadata(): Throwable? = runCatching {
        recorder.updateSourceDeviceMetadata(source.verifiedMetadata.asSessionMetadata())
    }.exceptionOrNull()
}

private val SensorLabUiState.isActive: Boolean
    get() = preparing || recording

private fun SensorSourceMetadata?.asSessionMetadata(): Map<String, String> {
    val metadata = this ?: return emptyMap()
    return buildMap {
        put("device_identity", metadata.deviceIdentity)
        metadata.protocolVersion?.let { put("protocol_version", it.toString()) }
        metadata.firmwareVersion?.let { put("firmware_version", it) }
        metadata.sensorModel?.let { put("sensor_model", it) }
        if (metadata.supportedRatesHz.isNotEmpty()) {
            put("supported_rates_hz", metadata.supportedRatesHz.joinToString(","))
        }
        metadata.activeRateHz?.let { put("active_rate_hz", it.toString()) }
        metadata.accelerometerRangeG?.let { put("accelerometer_range_g", it.toString()) }
        metadata.gyroscopeRangeDps?.let { put("gyroscope_range_dps", it.toString()) }
        metadata.packetBytes?.let { put("packet_bytes", it.toString()) }
        metadata.sampleReadMode?.let { put("sample_read_mode", it) }
        metadata.rawCapabilities?.let { put("raw_capabilities", it) }
        metadata.deviceDroppedSamples?.let { put("device_dropped_samples", it.toString()) }
        metadata.receiverMissingSamples?.let { put("receiver_missing_samples", it.toString()) }
        metadata.timeSyncMethod?.let { put("time_sync_method", it) }
        metadata.timeSyncUncertaintyNs?.let { put("time_sync_uncertainty_ns", it.toString()) }
    }
}
