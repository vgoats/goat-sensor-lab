package com.vgoats.sensorlab.sensor

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test

class PhoneImuSourceTest {
    @Test
    fun selectsOnlyPrecedingGyroscopeSampleWithinTolerance() {
        val buffer = GyroscopeSampleBuffer(toleranceNs = 100)
        buffer.observe(1_000, floatArrayOf(1f, 2f, 3f))

        assertNull(buffer.preceding(999))
        assertArrayEquals(floatArrayOf(1f, 2f, 3f), buffer.preceding(1_100)!!.values, 0f)
        assertNull(buffer.preceding(1_101))
    }

    @Test
    fun outOfOrderDeliveryStillSelectsClosestPrecedingTimestamp() {
        val buffer = GyroscopeSampleBuffer(toleranceNs = 1_000)
        buffer.observe(2_000, floatArrayOf(2f, 2f, 2f))
        buffer.observe(1_000, floatArrayOf(1f, 1f, 1f))

        assertEquals(1_000L, buffer.preceding(1_500)?.timestampNs)
        assertEquals(2_000L, buffer.preceding(2_500)?.timestampNs)
    }

    @Test
    fun toleranceScalesWithRequestedSamplingPeriod() {
        assertEquals(600_000_000L, gyroscopeToleranceForRateNs(5))
        assertEquals(120_000_000L, gyroscopeToleranceForRateNs(25))
        assertEquals(100_000_000L, gyroscopeToleranceForRateNs(50))
    }

    @Test
    fun installationIdentityIsStableAndMustBePersisted() {
        var persisted: String? = null
        val generated = resolveInstallationId(
            existing = null,
            create = { "123E4567-E89B-12D3-A456-426614174000" },
            persist = { persisted = it; true },
        )
        assertEquals("123e4567-e89b-12d3-a456-426614174000", generated)
        assertEquals(generated, persisted)

        var generatedAgain = false
        val restored = resolveInstallationId(
            existing = generated,
            create = { generatedAgain = true; "unused" },
            persist = { false },
        )
        assertEquals(generated, restored)
        assertEquals(false, generatedAgain)

        assertThrows(IllegalStateException::class.java) {
            resolveInstallationId(
                existing = null,
                create = { "123e4567-e89b-12d3-a456-426614174001" },
                persist = { false },
            )
        }
    }
}
