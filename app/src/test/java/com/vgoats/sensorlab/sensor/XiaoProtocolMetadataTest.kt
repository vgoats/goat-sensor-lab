package com.vgoats.sensorlab.sensor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

class XiaoProtocolMetadataTest {
    private val validCapabilities =
        """{"protocol":2,"firmware":"0.2.0","device_id":"GoatSensor-AABBCCDD00112233","imu":"LSM6DS3TR-C","rates_hz":[13,26],"accel_g":4,"gyro_dps":500,"packet_bytes":20,"sample_read":"sequential_axes"}"""

    @Test
    fun parsesAndValidatesObservedCapabilities() {
        val capabilities = XiaoCapabilities.parse(validCapabilities.toByteArray())
        capabilities.validate(26, "GoatSensor-AABBCCDD00112233")

        assertEquals(2, capabilities.protocolVersion)
        assertEquals("0.2.0", capabilities.firmwareVersion)
        assertEquals(listOf(13, 26), capabilities.supportedRatesHz)
        assertEquals("sequential_axes", capabilities.sampleReadMode)
    }

    @Test
    fun rejectsProtocolAndRequestedRateMismatches() {
        val wrongProtocol = validCapabilities.replace("\"protocol\":2", "\"protocol\":3")
        assertThrows(IllegalArgumentException::class.java) {
            XiaoCapabilities.parse(wrongProtocol.toByteArray())
                .validate(26, "GoatSensor-AABBCCDD00112233")
        }
        assertThrows(IllegalArgumentException::class.java) {
            XiaoCapabilities.parse(validCapabilities.toByteArray())
                .validate(50, "GoatSensor-AABBCCDD00112233")
        }
        assertThrows(IllegalArgumentException::class.java) {
            XiaoCapabilities.parse(validCapabilities.toByteArray())
                .validate(26, "GoatSensor-FFFFFFFFFFFFFFFF")
        }
        assertThrows(IllegalArgumentException::class.java) {
            XiaoCapabilities.parse(
                validCapabilities
                    .replace("\"imu\":\"LSM6DS3TR-C\"", "\"imu\":\"unavailable\"")
                    .toByteArray(),
            )
                .validate(26, "GoatSensor-AABBCCDD00112233")
        }
    }

    @Test
    fun decodesStatusAndUnsignedDropCounter() {
        val packet = ByteBuffer.allocate(XiaoStatus.PACKET_SIZE)
            .order(ByteOrder.LITTLE_ENDIAN)
            .put(2)
            .put(1)
            .putShort(13)
            .putInt(-1)
            .array()

        val status = XiaoStatus.decode(packet)
        assertTrue(status.streaming)
        assertEquals(13, status.sampleRateHz)
        assertEquals(0xffffffffL, status.droppedSamples)

        packet[1] = 0
        assertFalse(XiaoStatus.decode(packet).streaming)
    }

    @Test
    fun rejectsMalformedCapabilitiesAndStatus() {
        assertThrows(IllegalArgumentException::class.java) {
            XiaoCapabilities.parse("{}".toByteArray())
        }
        assertThrows(IllegalArgumentException::class.java) {
            XiaoStatus.decode(ByteArray(7))
        }
    }
}
