package com.vgoats.sensorlab.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.File

class SessionSummaryTest {
    @Test
    fun calculatesRateFromMonotonicSensorTime() {
        val summary = SessionSummary(
            sessionId = "session",
            directory = File("."),
            startedAtEpochMs = 0,
            endedAtEpochMs = 999_999,
            sampleCount = 101,
            firstSampleMonotonicNs = 4_000_000_000,
            lastSampleMonotonicNs = 8_000_000_000,
        )

        assertEquals(25.0, summary.achievedSampleRateHz()!!, 0.00001)
    }

    @Test
    fun doesNotInventRateWithoutTwoSamples() {
        val summary = SessionSummary("session", File("."), 0, 1, 1, 10, 10)
        assertNull(summary.achievedSampleRateHz())
    }
}
