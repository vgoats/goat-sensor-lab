package com.vgoats.sensorlab.sensor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BleProtocolGuardsTest {
    @Test
    fun boardIdentityRequiresExactConfiguredHardwareId() {
        assertTrue(
            GoatSensorIdentity.matches(
                "aabbccdd00112233",
                "GoatSensor-AABBCCDD00112233",
            ),
        )
        assertFalse(
            GoatSensorIdentity.matches(
                "AABBCCDD00112233",
                "GoatSensor-AABBCCDD00112234",
            ),
        )
    }

    @Test
    fun boardIdentityAcceptsPastedNameAndIgnoresTrailingText() {
        assertEquals(
            "911806CBE88F40D2",
            GoatSensorIdentity.normalize("GoatSensor-911806CBE88F40D2 BY"),
        )
        assertTrue(
            GoatSensorIdentity.matches(
                "911806CBE88F40D2 BY",
                "GoatSensor-911806CBE88F40D2",
            ),
        )
    }

    @Test
    fun sequenceTrackerCountsLossAndHandlesUint32Wrap() {
        val tracker = UnsignedSequenceTracker()
        assertTrue(tracker.observe(0xfffffffeL).accepted)
        assertTrue(tracker.observe(1L).accepted)
        assertEquals(2L, tracker.totalMissing)
    }

    @Test
    fun sequenceTrackerRejectsDuplicatesAndBackwardPackets() {
        val tracker = UnsignedSequenceTracker()
        tracker.observe(10)
        assertFalse(tracker.observe(10).accepted)
        assertFalse(tracker.observe(9).accepted)
        assertEquals(0L, tracker.totalMissing)
    }

    @Test
    fun sequenceTrackerCountsLossFromFreshAnchor() {
        val tracker = UnsignedSequenceTracker()
        tracker.expectNext(100)
        val observation = tracker.observe(103)
        assertTrue(observation.accepted)
        assertEquals(3L, observation.missingSincePrevious)
        assertEquals(3L, tracker.totalMissing)
    }
}
