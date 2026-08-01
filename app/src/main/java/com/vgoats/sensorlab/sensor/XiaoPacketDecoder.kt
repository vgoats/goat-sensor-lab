package com.vgoats.sensorlab.sensor

import com.vgoats.sensorlab.domain.SensorFrame
import com.vgoats.sensorlab.domain.SensorSourceType
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.PI

object XiaoPacketDecoder {
    const val PACKET_SIZE = 20
    const val TIME_ANCHOR_SIZE = 12
    const val PROTOCOL_VERSION = 2
    private const val GRAVITY_MS2 = 9.80665

    fun decode(
        bytes: ByteArray,
        deviceId: String,
        anchorWallTimeEpochMs: Long,
        anchorMonotonicTimeNs: Long,
        anchorBoardUptimeMs: Long,
        rssiDbm: Int? = null,
    ): SensorFrame {
        require(bytes.size == PACKET_SIZE) { "Expected $PACKET_SIZE bytes, got ${bytes.size}" }
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        val sequence = buffer.int.toLong() and 0xffffffffL
        val boardUptimeMs = buffer.int.toLong() and 0xffffffffL
        val ax = buffer.short.toDouble() / 1000.0 * GRAVITY_MS2
        val ay = buffer.short.toDouble() / 1000.0 * GRAVITY_MS2
        val az = buffer.short.toDouble() / 1000.0 * GRAVITY_MS2
        val gx = centiDegreesToRad(buffer.short.toDouble())
        val gy = centiDegreesToRad(buffer.short.toDouble())
        val gz = centiDegreesToRad(buffer.short.toDouble())
        val millisecondsFromAnchor = (boardUptimeMs - anchorBoardUptimeMs) and 0xffffffffL
        val sampleTimeNs = anchorMonotonicTimeNs + millisecondsFromAnchor * 1_000_000
        val sampleWallTimeMs = anchorWallTimeEpochMs + millisecondsFromAnchor

        return SensorFrame(
            source = SensorSourceType.XIAO_NRF52840_SENSE,
            deviceId = deviceId,
            sequence = sequence,
            wallTimeEpochMs = sampleWallTimeMs,
            monotonicTimeNs = sampleTimeNs,
            sourceUptimeMs = boardUptimeMs,
            gyroscopeTimeNs = sampleTimeNs,
            accelerationXMs2 = ax,
            accelerationYMs2 = ay,
            accelerationZMs2 = az,
            gyroscopeXRadS = gx,
            gyroscopeYRadS = gy,
            gyroscopeZRadS = gz,
            rssiDbm = rssiDbm,
        )
    }

    fun decodeTimeAnchor(bytes: ByteArray): BoardTimeAnchor {
        require(bytes.size == TIME_ANCHOR_SIZE) {
            "Expected $TIME_ANCHOR_SIZE anchor bytes, got ${bytes.size}"
        }
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        val version = buffer.get().toInt() and 0xff
        require(version == PROTOCOL_VERSION) { "Unsupported protocol version: $version" }
        buffer.get() // flags
        buffer.short // reserved
        return BoardTimeAnchor(
            sequence = buffer.int.toLong() and 0xffffffffL,
            boardUptimeMs = buffer.int.toLong() and 0xffffffffL,
        )
    }

    private fun centiDegreesToRad(value: Double): Double = value / 100.0 * PI / 180.0
}

data class BoardTimeAnchor(
    val sequence: Long,
    val boardUptimeMs: Long,
)
