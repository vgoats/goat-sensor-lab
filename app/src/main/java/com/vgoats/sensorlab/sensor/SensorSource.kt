package com.vgoats.sensorlab.sensor

import com.vgoats.sensorlab.domain.SensorFrame
import com.vgoats.sensorlab.domain.SensorSourceType

data class SensorAvailability(
    val available: Boolean,
    val description: String,
)

data class SensorSourceMetadata(
    val deviceIdentity: String,
    val protocolVersion: Int? = null,
    val firmwareVersion: String? = null,
    val sensorModel: String? = null,
    val supportedRatesHz: List<Int> = emptyList(),
    val activeRateHz: Int? = null,
    val accelerometerRangeG: Int? = null,
    val gyroscopeRangeDps: Int? = null,
    val packetBytes: Int? = null,
    val sampleReadMode: String? = null,
    val rawCapabilities: String? = null,
    val deviceDroppedSamples: Long? = null,
    val receiverMissingSamples: Long? = null,
    val timeSyncMethod: String? = null,
    val timeSyncUncertaintyNs: Long? = null,
)

interface SensorSource {
    val type: SensorSourceType
    val availability: SensorAvailability
    val verifiedMetadata: SensorSourceMetadata?
        get() = null

    fun start(
        sampleRateHz: Int,
        targetDeviceId: String? = null,
        onFrame: (SensorFrame) -> Unit,
        onStatus: (String) -> Unit = {},
        onReady: () -> Unit = {},
        onError: (String) -> Unit = {},
    ): Result<Unit>
    fun stop()
}
