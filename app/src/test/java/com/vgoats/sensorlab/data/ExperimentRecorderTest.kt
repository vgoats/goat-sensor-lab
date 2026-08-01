package com.vgoats.sensorlab.data

import com.vgoats.sensorlab.domain.BehaviorLabels
import com.vgoats.sensorlab.domain.IngestiveBehavior
import com.vgoats.sensorlab.domain.Placement
import com.vgoats.sensorlab.domain.SensorFrame
import com.vgoats.sensorlab.domain.SensorSourceType
import com.vgoats.sensorlab.domain.SessionConfig
import com.vgoats.sensorlab.domain.Species
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class ExperimentRecorderTest {
    @get:Rule
    val temporaryFolder = TemporaryFolder()

    @Test
    fun delayedFrameUsesLabelEffectiveAtSampleTime() {
        val clock = FakeRecorderClock(wallMs = 1_700_000_000_000, monotonicNs = 100)
        val recorder = recorder(clock)
        val summary = recorder.start(config())
        recorder.append(frame(sequence = 0, monotonicNs = 100))

        clock.monotonicNs = 200
        recorder.updateLabels(BehaviorLabels(ingestive = IngestiveBehavior.FEEDING))
        recorder.append(frame(sequence = 1, monotonicNs = 150))
        recorder.append(frame(sequence = 2, monotonicNs = 200))
        recorder.append(frame(sequence = 3, monotonicNs = 250))
        clock.monotonicNs = 300
        val completed = recorder.stop()

        val rows = File(summary.directory, "samples.csv").readLines().drop(1)
        assertEquals(
            listOf("UNKNOWN", "UNKNOWN", "FEEDING", "FEEDING"),
            rows.map { it.split(',')[21] },
        )
        val events = File(summary.directory, "events.csv").readLines()
        assertTrue(events.any { it.contains(",200,") && it.contains(",label_change,FEEDING,") })
        assertEquals(100L, completed?.firstSampleMonotonicNs)
        assertEquals(250L, completed?.lastSampleMonotonicNs)
    }

    @Test
    fun rejectsOutOfOrderFramesBeforeWritingAnInvalidDataset() {
        val recorder = recorder(FakeRecorderClock(wallMs = 5_000, monotonicNs = 100))
        recorder.start(config())
        recorder.append(frame(sequence = 10, monotonicNs = 1_000))

        assertThrows(IllegalStateException::class.java) {
            recorder.append(frame(sequence = 11, monotonicNs = 999))
        }
        assertThrows(IllegalStateException::class.java) {
            recorder.append(frame(sequence = 10, monotonicNs = 1_001))
        }
        recorder.stop()
    }

    @Test
    fun rowsAreVisibleBeforeStopAndMetadataIsCheckpointedAtomically() {
        val clock = FakeRecorderClock(wallMs = 10_000, monotonicNs = 1_000)
        val recorder = recorder(clock)
        val summary = recorder.start(config())
        recorder.append(frame(sequence = 0, monotonicNs = 1_100))
        recorder.append(frame(sequence = 1, monotonicNs = 1_200))

        assertEquals(2L, Csv.dataRecordCount(File(summary.directory, "samples.csv")))
        val metadata = JSONObject(File(summary.directory, "session.json").readText())
        assertEquals("RECORDING", metadata.getString("recording_state"))
        assertEquals(1L, metadata.getLong("sample_count"))
        assertFalse(summary.directory.listFiles().orEmpty().any { it.name.endsWith(".tmp") })

        recorder.stop()
        val completed = JSONObject(File(summary.directory, "session.json").readText())
        assertEquals("COMPLETED", completed.getString("recording_state"))
        assertEquals(2L, completed.getLong("sample_count"))
    }

    @Test
    fun interruptedSessionIsReconciledAndRemainsExportable() {
        val root = temporaryFolder.newFolder("experiments")
        val clock = FakeRecorderClock(wallMs = 20_000, monotonicNs = 1_000)
        val interrupted = ExperimentRecorder(root, clock, "test")
        val summary = interrupted.start(config())
        interrupted.append(frame(sequence = 0, monotonicNs = 1_100))
        interrupted.append(frame(sequence = 1, monotonicNs = 1_200))

        clock.wallMs = 30_000
        val restarted = ExperimentRecorder(root, clock, "test")
        val recovered = restarted.recoverIncompleteSessions()

        assertEquals(1, recovered.size)
        assertEquals(2L, recovered.single().sampleCount)
        assertEquals(summary.sessionId, restarted.latestExportableSession()?.sessionId)
        val metadata = JSONObject(File(summary.directory, "session.json").readText())
        assertEquals("INCOMPLETE_RECOVERED", metadata.getString("recording_state"))
        assertEquals(2L, metadata.getLong("sample_count"))
        val firstRecoveredAt = metadata.getLong("recovered_at_epoch_ms")

        clock.wallMs = 40_000
        assertEquals(2L, restarted.recoverIncompleteSessions().single().sampleCount)
        val metadataAfterSecondLaunch = JSONObject(File(summary.directory, "session.json").readText())
        assertEquals(firstRecoveredAt, metadataAfterSecondLaunch.getLong("recovered_at_epoch_ms"))

        interrupted.stop()
    }

    @Test
    fun recoveryPreservesCompleteQuotedSamplesAndRemovesTruncatedQuotedTail() {
        val root = temporaryFolder.newFolder("quoted-sample-recovery")
        val clock = FakeRecorderClock(wallMs = 31_000, monotonicNs = 1_000)
        val interrupted = ExperimentRecorder(root, clock, "test")
        val summary = interrupted.start(config(animalId = "GOAT,\n001"))
        interrupted.append(frame(sequence = 0, monotonicNs = 1_100))
        interrupted.append(frame(sequence = 1, monotonicNs = 1_200))
        File(summary.directory, "samples.csv").appendText("\"truncated\nquoted")

        clock.wallMs = 32_000
        val restarted = ExperimentRecorder(root, clock, "test")
        val recovered = restarted.recoverIncompleteSessions().single()
        val inspection = Csv.inspectCanonical(
            File(summary.directory, "samples.csv"),
            SessionIntegrity.sampleHeader,
            SessionIntegrity.SAMPLE_SESSION_ID_INDEX,
        )

        assertEquals(2L, recovered.sampleCount)
        assertTrue(inspection.canonical)
        assertEquals(2L, inspection.dataRecordCount)
        assertEquals("GOAT,\n001", inspection.firstDataRecord?.get(2))
        assertTrue(
            File(summary.directory, Csv.QUARANTINE_DIRECTORY).listFiles().orEmpty()
                .any { it.name.startsWith("samples.csv.") && it.name.endsWith(".corrupt") },
        )
        File(summary.directory, "session-recovery.json").writeText("{}")
        File(summary.directory, "samples.csv.corrupt").writeText("not export data")
        File(summary.directory, ".session.json.tmp").writeText("temporary")
        assertEquals(
            listOf("events.csv", "samples.csv", "session.json"),
            SessionExporter.filesForExport(summary.directory).map(File::getName),
        )
    }

    @Test
    fun exactWidthUnterminatedSampleIsTrimmedAndSessionBecomesNonExportable() {
        val root = temporaryFolder.newFolder("unterminated-sample-recovery")
        val clock = FakeRecorderClock(wallMs = 32_500, monotonicNs = 1_000)
        val interrupted = ExperimentRecorder(root, clock, "test")
        val summary = interrupted.start(config())
        interrupted.append(frame(sequence = 0, monotonicNs = 1_100))
        val samplesFile = File(summary.directory, "samples.csv")
        val originalRecords = samplesFile.readLines()
        assertEquals(25, originalRecords[1].split(',').size)
        samplesFile.writeText("${originalRecords[0]}\n${originalRecords[1]}")

        clock.wallMs = 32_600
        val restarted = ExperimentRecorder(root, clock, "test")
        assertTrue(restarted.recoverIncompleteSessions().isEmpty())
        val samples = Csv.inspectCanonical(
            samplesFile,
            SessionIntegrity.sampleHeader,
            SessionIntegrity.SAMPLE_SESSION_ID_INDEX,
        )
        val metadata = JSONObject(File(summary.directory, "session.json").readText())

        assertTrue(samples.canonical)
        assertEquals(0L, samples.dataRecordCount)
        assertFalse(metadata.getBoolean("exportable"))
        assertTrue(metadata.getString("non_exportable_reason").contains("no recoverable data"))
        assertTrue(
            File(summary.directory, Csv.QUARANTINE_DIRECTORY).listFiles().orEmpty()
                .any { it.name.startsWith("samples.csv.") && it.name.endsWith(".corrupt") },
        )
        assertThrows(IllegalArgumentException::class.java) {
            SessionExporter.filesForExport(summary.directory)
        }
    }

    @Test
    fun exactWidthUnterminatedEventIsTrimmedWhileCompletePrefixRemainsExportable() {
        val root = temporaryFolder.newFolder("partial-event-recovery")
        val clock = FakeRecorderClock(wallMs = 33_000, monotonicNs = 1_000)
        val interrupted = ExperimentRecorder(root, clock, "test")
        val summary = interrupted.start(config())
        interrupted.append(frame(sequence = 0, monotonicNs = 1_100))
        val unterminatedEvent = Csv.row(
            33,
            44,
            summary.sessionId,
            "label_change",
            "UNKNOWN",
            "UNKNOWN",
            "NORMAL",
            false,
        )
        assertEquals(8, unterminatedEvent.split(',').size)
        File(summary.directory, "events.csv").appendText(unterminatedEvent)

        clock.wallMs = 34_000
        val restarted = ExperimentRecorder(root, clock, "test")
        assertEquals(1L, restarted.recoverIncompleteSessions().single().sampleCount)
        val events = Csv.inspectCanonical(
            File(summary.directory, "events.csv"),
            SessionIntegrity.eventHeader,
            SessionIntegrity.EVENT_SESSION_ID_INDEX,
        )

        assertTrue(events.canonical)
        assertEquals(1L, events.dataRecordCount)
        assertEquals("session_start", events.firstDataRecord?.get(3))
        assertTrue(
            File(summary.directory, Csv.QUARANTINE_DIRECTORY).listFiles().orEmpty()
                .any { it.name.startsWith("events.csv.") && it.name.endsWith(".corrupt") },
        )
        assertEquals(3, SessionExporter.filesForExport(summary.directory).size)
    }

    @Test
    fun malformedCsvHeaderPermanentlyMarksRecoveredSessionNonExportable() {
        val root = temporaryFolder.newFolder("bad-header-recovery")
        val clock = FakeRecorderClock(wallMs = 35_000, monotonicNs = 1_000)
        val interrupted = ExperimentRecorder(root, clock, "test")
        val summary = interrupted.start(config())
        interrupted.append(frame(sequence = 0, monotonicNs = 1_100))
        val samplesFile = File(summary.directory, "samples.csv")
        samplesFile.writeText(samplesFile.readText().replaceFirst("schema_version", "wrong_header"))

        clock.wallMs = 36_000
        val restarted = ExperimentRecorder(root, clock, "test")
        assertTrue(restarted.recoverIncompleteSessions().isEmpty())
        assertNull(restarted.latestExportableSession())
        val metadata = JSONObject(File(summary.directory, "session.json").readText())
        assertFalse(metadata.getBoolean("exportable"))
        assertTrue(metadata.getString("non_exportable_reason").contains("header"))
        assertThrows(IllegalArgumentException::class.java) {
            SessionExporter.filesForExport(summary.directory)
        }
        assertTrue(
            File(summary.directory, Csv.QUARANTINE_DIRECTORY).listFiles().orEmpty()
                .any { it.name.startsWith("samples.csv.") && it.name.endsWith(".corrupt") },
        )
    }

    @Test
    fun truncatedSessionJsonIsQuarantinedAndReconstructedWithExplicitMissingness() {
        val root = temporaryFolder.newFolder("metadata-recovery")
        val clock = FakeRecorderClock(wallMs = 37_000, monotonicNs = 1_000)
        val interrupted = ExperimentRecorder(root, clock, "test")
        val summary = interrupted.start(config())
        interrupted.append(frame(sequence = 0, monotonicNs = 1_100))
        File(summary.directory, "session.json").writeText("{\"schema_version\":1,")

        clock.wallMs = 38_000
        val restarted = ExperimentRecorder(root, clock, "test")
        val recovered = restarted.recoverIncompleteSessions().single()
        val metadata = JSONObject(File(summary.directory, "session.json").readText())

        assertEquals(summary.sessionId, recovered.sessionId)
        assertEquals("RECONSTRUCTED_FROM_CANONICAL_SAMPLES", metadata.getString("metadata_origin"))
        assertEquals("GOAT-001", metadata.getString("animal_id"))
        assertTrue(metadata.getBoolean("exportable"))
        assertTrue(
            (0 until metadata.getJSONArray("recovery_missing_fields").length())
                .map { metadata.getJSONArray("recovery_missing_fields").getString(it) }
                .contains("annotator_id"),
        )
        assertNotNull(metadata.getJSONObject("source_device_metadata"))
        assertTrue(
            File(summary.directory, Csv.QUARANTINE_DIRECTORY).listFiles().orEmpty()
                .any { it.name.startsWith("session.json.") && it.name.endsWith(".corrupt") },
        )
        assertEquals(3, SessionExporter.filesForExport(summary.directory).size)
    }

    @Test
    fun metadataSerializerPreservesJsonControlCharactersAndSensorMetadata() {
        val clock = FakeRecorderClock(wallMs = 40_000, monotonicNs = 1_000)
        val recorder = recorder(clock)
        val notes = "tab\tcontrol\u0001line\nquote\""
        val summary = recorder.start(
            config(
                notes = notes,
                sourceDeviceMetadata = mapOf("sensor_model" to "Vendor \"IMU\"")
            ),
        )

        val metadata = JSONObject(File(summary.directory, "session.json").readText())
        assertEquals(notes, metadata.getString("notes"))
        assertEquals(
            "Vendor \"IMU\"",
            metadata.getJSONObject("source_device_metadata").getString("sensor_model"),
        )
        recorder.stop()
    }

    @Test
    fun observedSensorMetadataReplacesExpectationsAndRetainsDropCounterBounds() {
        val clock = FakeRecorderClock(wallMs = 45_000, monotonicNs = 1_000)
        val recorder = recorder(clock)
        val summary = recorder.start(config())
        recorder.updateSourceDeviceMetadata(
            mapOf(
                "protocol_version" to "2",
                "firmware_version" to "0.2.0",
                "accelerometer_range_g" to "4",
                "gyroscope_range_dps" to "500",
                "device_dropped_samples" to "7",
            ),
        )
        recorder.updateSourceDeviceMetadata(
            mapOf(
                "protocol_version" to "2",
                "firmware_version" to "0.2.1",
                "device_dropped_samples" to "11",
            ),
        )

        val metadata = JSONObject(File(summary.directory, "session.json").readText())
        val observed = metadata.getJSONObject("source_device_metadata")
        assertEquals(2, metadata.getInt("ble_protocol_version"))
        assertEquals("0.2.1", metadata.getString("observed_firmware_version"))
        assertTrue(metadata.isNull("expected_firmware_version"))
        assertEquals("7", observed.getString("device_dropped_samples_start"))
        assertEquals("11", observed.getString("device_dropped_samples_end"))
        recorder.stop()
    }

    @Test
    fun failedStartDoesNotLeaveAnActiveSession() {
        val invalidRoot = temporaryFolder.newFile("not-a-directory")
        val recorder = ExperimentRecorder(
            invalidRoot,
            FakeRecorderClock(wallMs = 50_000, monotonicNs = 1_000),
            "test",
        )

        assertThrows(IllegalStateException::class.java) { recorder.start(config()) }
        assertNull(recorder.activeSession)
    }

    private fun recorder(clock: FakeRecorderClock): ExperimentRecorder = ExperimentRecorder(
        temporaryFolder.newFolder("experiments-${clock.wallMs}"),
        clock,
        "test",
    )

    private fun config(
        animalId: String = "GOAT-001",
        notes: String = "",
        sourceDeviceMetadata: Map<String, String> = emptyMap(),
    ) = SessionConfig(
        animalId = animalId,
        species = Species.GOAT,
        placement = Placement.PHONE_HANDHELD_TEST,
        sampleRateHz = 25,
        notes = notes,
        source = SensorSourceType.ANDROID_PHONE,
        expectedDeviceId = null,
        annotatorId = "observer-1",
        shedId = "shed-1",
        cameraIds = "camera-1",
        sourceDeviceMetadata = sourceDeviceMetadata,
    )

    private fun frame(sequence: Long, monotonicNs: Long) = SensorFrame(
        source = SensorSourceType.ANDROID_PHONE,
        deviceId = "AndroidPhone-test",
        sequence = sequence,
        wallTimeEpochMs = 1_700_000_000_000 + sequence,
        monotonicTimeNs = monotonicNs,
        gyroscopeTimeNs = monotonicNs,
        accelerationXMs2 = 0.0,
        accelerationYMs2 = 0.0,
        accelerationZMs2 = 9.80665,
        gyroscopeXRadS = 0.0,
        gyroscopeYRadS = 0.0,
        gyroscopeZRadS = 0.0,
    )
}

private class FakeRecorderClock(
    var wallMs: Long,
    var monotonicNs: Long,
) : RecorderClock {
    override fun wallTimeEpochMs(): Long = wallMs
    override fun monotonicTimeNs(): Long = monotonicNs
}
