package com.vgoats.sensorlab.data

import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class CsvTest {
    @get:Rule
    val temporaryFolder = TemporaryFolder()

    @Test
    fun escapesCommasQuotesAndNewlines() {
        assertEquals("plain", Csv.escape("plain"))
        assertEquals("\"goat, sheep\"", Csv.escape("goat, sheep"))
        assertEquals("\"said \"\"feed\"\"\"", Csv.escape("said \"feed\""))
        assertEquals("\"line1\nline2\"", Csv.escape("line1\nline2"))
    }

    @Test
    fun preservesEmptyColumns() {
        assertEquals("a,,3", Csv.row("a", null, 3))
    }

    @Test
    fun countsOnlyCompleteRecordsAndRespectsQuotedNewlines() {
        val file = temporaryFolder.newFile("samples.csv")
        file.writeText(
            "a,b\n" +
                "1,plain\n" +
                "2,\"two\nlines\"\n" +
                "3,incomplete",
        )

        assertEquals(2L, Csv.dataRecordCount(file))
    }

    @Test
    fun canonicalInspectionAcceptsCrLfRecordsAndQuotedNewlines() {
        val file = temporaryFolder.newFile("events.csv")
        file.writeText("session_id,note\r\nsession-1,\"two\nlines\"\r\n")

        val inspection = Csv.inspectCanonical(
            file = file,
            expectedHeader = listOf("session_id", "note"),
            identityColumnIndex = 0,
        )

        assertEquals(true, inspection.canonical)
        assertEquals(1L, inspection.dataRecordCount)
        assertEquals(listOf("session-1", "two\nlines"), inspection.firstDataRecord)
    }
}
