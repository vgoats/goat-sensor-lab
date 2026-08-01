package com.vgoats.sensorlab.sensor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.PI

class XiaoPacketDecoderTest {
    @Test
    fun decodesVersionTwoLittleEndianPacketUsingBoardUptime() {
        val packet = ByteBuffer.allocate(XiaoPacketDecoder.PACKET_SIZE)
            .order(ByteOrder.LITTLE_ENDIAN)
            .putInt(70_000)
            .putInt(51_234)
            .putShort(1_000)
            .putShort((-500).toShort())
            .putShort(250)
            .putShort(9_000)
            .putShort((-4_500).toShort())
            .putShort(18_000)
            .array()

        val frame = XiaoPacketDecoder.decode(
            packet,
            "GoatSensor-AABBCCDD00112233",
            999_000,
            8_000_000_000,
            50_000,
            -61,
        )

        assertEquals(70_000L, frame.sequence)
        assertEquals(9_234_000_000L, frame.monotonicTimeNs)
        assertEquals(1_000_234L, frame.wallTimeEpochMs)
        assertEquals(51_234L, frame.sourceUptimeMs)
        assertEquals(9.80665, frame.accelerationXMs2, 0.00001)
        assertEquals(-4.903325, frame.accelerationYMs2, 0.00001)
        assertEquals(PI / 2, frame.gyroscopeXRadS!!, 0.00001)
        assertEquals(-PI / 4, frame.gyroscopeYRadS!!, 0.00001)
        assertEquals(PI, frame.gyroscopeZRadS!!, 0.00001)
        assertEquals(-61, frame.rssiDbm)
    }

    @Test
    fun decodesAnchorAndRejectsUnknownVersion() {
        val anchor = ByteBuffer.allocate(XiaoPacketDecoder.TIME_ANCHOR_SIZE)
            .order(ByteOrder.LITTLE_ENDIAN)
            .put(2)
            .put(0)
            .putShort(0)
            .putInt(71)
            .putInt(50_000)
            .array()
        assertEquals(71L, XiaoPacketDecoder.decodeTimeAnchor(anchor).sequence)
        assertEquals(50_000L, XiaoPacketDecoder.decodeTimeAnchor(anchor).boardUptimeMs)

        anchor[0] = 3
        assertThrows(IllegalArgumentException::class.java) {
            XiaoPacketDecoder.decodeTimeAnchor(anchor)
        }
    }

    @Test
    fun uptimeWrapStillProducesForwardTime() {
        val packet = ByteBuffer.allocate(XiaoPacketDecoder.PACKET_SIZE)
            .order(ByteOrder.LITTLE_ENDIAN)
            .putInt(1)
            .putInt(25)
            .putShort(0).putShort(0).putShort(1_000)
            .putShort(0).putShort(0).putShort(0)
            .array()

        val frame = XiaoPacketDecoder.decode(
            packet,
            "GoatSensor-01",
            5_000,
            10_000_000_000,
            0xfffffff0L,
        )

        assertEquals(41L, frame.wallTimeEpochMs - 5_000)
        assertEquals(10_041_000_000L, frame.monotonicTimeNs)
    }

    @Test
    fun rejectsTruncatedPacket() {
        assertThrows(IllegalArgumentException::class.java) {
            XiaoPacketDecoder.decode(ByteArray(19), "xiao-01", 0, 0, 0)
        }
    }
}
