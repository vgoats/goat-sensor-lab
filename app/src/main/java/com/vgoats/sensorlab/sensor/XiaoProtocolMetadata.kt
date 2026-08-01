package com.vgoats.sensorlab.sensor

import java.nio.ByteBuffer
import java.nio.ByteOrder

internal data class XiaoCapabilities(
    val protocolVersion: Int,
    val firmwareVersion: String,
    val deviceIdentity: String,
    val imu: String,
    val supportedRatesHz: List<Int>,
    val accelerometerRangeG: Int,
    val gyroscopeRangeDps: Int,
    val packetBytes: Int,
    val sampleReadMode: String,
    val rawJson: String,
) {
    fun validate(requestedRateHz: Int, expectedDeviceIdentity: String) {
        require(protocolVersion == XiaoPacketDecoder.PROTOCOL_VERSION) {
            "Unsupported XIAO protocol $protocolVersion"
        }
        require(requestedRateHz in supportedRatesHz) {
            "XIAO does not support $requestedRateHz Hz"
        }
        require(packetBytes == XiaoPacketDecoder.PACKET_SIZE) {
            "Unsupported XIAO packet size $packetBytes"
        }
        require(accelerometerRangeG == 4) {
            "Unsupported XIAO accelerometer range ${accelerometerRangeG}g"
        }
        require(gyroscopeRangeDps == 500) {
            "Unsupported XIAO gyroscope range ${gyroscopeRangeDps} dps"
        }
        require(sampleReadMode == "sequential_axes") {
            "Unsupported XIAO sample read mode $sampleReadMode"
        }
        require(deviceIdentity == expectedDeviceIdentity) {
            "XIAO capability identity $deviceIdentity does not match $expectedDeviceIdentity"
        }
    }

    fun toMetadata(
        deviceIdentity: String,
        status: XiaoStatus? = null,
        timeSyncUncertaintyNs: Long? = null,
        receiverMissingSamples: Long? = null,
    ) = SensorSourceMetadata(
        deviceIdentity = deviceIdentity,
        protocolVersion = protocolVersion,
        firmwareVersion = firmwareVersion,
        sensorModel = imu,
        supportedRatesHz = supportedRatesHz,
        activeRateHz = status?.sampleRateHz,
        accelerometerRangeG = accelerometerRangeG,
        gyroscopeRangeDps = gyroscopeRangeDps,
        packetBytes = packetBytes,
        sampleReadMode = sampleReadMode,
        rawCapabilities = rawJson,
        deviceDroppedSamples = status?.droppedSamples,
        receiverMissingSamples = receiverMissingSamples,
        timeSyncMethod = "control_request_midpoint",
        timeSyncUncertaintyNs = timeSyncUncertaintyNs,
    )

    companion object {
        fun parse(bytes: ByteArray): XiaoCapabilities {
            val json = bytes.toString(Charsets.UTF_8).trim().trimEnd('\u0000')
            require(json.startsWith('{') && json.endsWith('}')) {
                "Capabilities are not a JSON object"
            }
            return XiaoCapabilities(
                protocolVersion = json.requiredInt("protocol"),
                firmwareVersion = json.requiredString("firmware"),
                deviceIdentity = json.requiredString("device_id"),
                imu = json.requiredString("imu"),
                supportedRatesHz = json.requiredIntArray("rates_hz"),
                accelerometerRangeG = json.requiredInt("accel_g"),
                gyroscopeRangeDps = json.requiredInt("gyro_dps"),
                packetBytes = json.requiredInt("packet_bytes"),
                sampleReadMode = json.requiredString("sample_read"),
                rawJson = json,
            )
        }
    }
}

internal data class XiaoStatus(
    val protocolVersion: Int,
    val streaming: Boolean,
    val sampleRateHz: Int,
    val droppedSamples: Long,
) {
    companion object {
        const val PACKET_SIZE = 8

        fun decode(bytes: ByteArray): XiaoStatus {
            require(bytes.size == PACKET_SIZE) {
                "Expected $PACKET_SIZE status bytes, got ${bytes.size}"
            }
            val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
            val version = buffer.get().toInt() and 0xff
            val flags = buffer.get().toInt() and 0xff
            val rate = buffer.short.toInt() and 0xffff
            val dropped = buffer.int.toLong() and 0xffffffffL
            require(version == XiaoPacketDecoder.PROTOCOL_VERSION) {
                "Unsupported XIAO status protocol $version"
            }
            return XiaoStatus(version, flags and 1 != 0, rate, dropped)
        }
    }
}

private fun String.requiredInt(key: String): Int {
    val match = Regex("\\\"${Regex.escape(key)}\\\"\\s*:\\s*(-?\\d+)").find(this)
    return requireNotNull(match) { "Missing integer capability $key" }.groupValues[1].toInt()
}

private fun String.requiredString(key: String): String {
    val match = Regex("\\\"${Regex.escape(key)}\\\"\\s*:\\s*\\\"([^\\\"\\\\]*)\\\"").find(this)
    return requireNotNull(match) { "Missing string capability $key" }.groupValues[1]
}

private fun String.requiredIntArray(key: String): List<Int> {
    val match = Regex("\\\"${Regex.escape(key)}\\\"\\s*:\\s*\\[([^]]*)]").find(this)
    val body = requireNotNull(match) { "Missing integer-array capability $key" }.groupValues[1]
    val values = body.split(',').map { it.trim() }.filter { it.isNotEmpty() }
    require(values.isNotEmpty() && values.all { it.matches(Regex("-?\\d+")) }) {
        "Invalid integer-array capability $key"
    }
    return values.map(String::toInt)
}
