package com.vgoats.sensorlab.data

import java.io.BufferedWriter
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.io.PushbackReader
import java.nio.charset.StandardCharsets
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption

internal data class CanonicalCsvInspection(
    val canonical: Boolean,
    val sourceHeaderValid: Boolean,
    val dataRecordCount: Long,
    val firstDataRecord: List<String>?,
    val lastDataRecord: List<String>?,
    val identityValue: String?,
    val identityConsistent: Boolean,
    val issue: String?,
    val repaired: Boolean = false,
    val quarantinedOriginal: File? = null,
)

object Csv {
    private enum class ParserState { UNQUOTED, QUOTED, AFTER_QUOTE }

    fun row(vararg values: Any?): String = values.joinToString(",") { escape(it?.toString().orEmpty()) }

    fun escape(value: String): String {
        if (value.none { it == ',' || it == '"' || it == '\n' || it == '\r' }) return value
        return "\"${value.replace("\"", "\"\"")}\""
    }

    /** Count complete records for diagnostics. Canonical recovery uses [inspectCanonical]. */
    fun dataRecordCount(file: File): Long {
        if (!file.isFile) return 0
        var records = 0L
        scanRecords(file) {
            records++
            true
        }
        return (records - 1).coerceAtLeast(0)
    }

    internal fun inspectCanonical(
        file: File,
        expectedHeader: List<String>,
        identityColumnIndex: Int,
    ): CanonicalCsvInspection = canonicalScan(
        file = file,
        expectedHeader = expectedHeader,
        identityColumnIndex = identityColumnIndex,
        repaired = false,
        quarantinedOriginal = null,
        canonicalWriter = null,
    )

    /**
     * Preserve a corrupt source in a hidden quarantine and atomically replace it with the valid
     * prefix. The parser stops at the first malformed, truncated, or incorrectly-shaped record.
     */
    internal fun recoverCanonical(
        file: File,
        expectedHeader: List<String>,
        identityColumnIndex: Int,
        recoveryEpochMs: Long,
    ): CanonicalCsvInspection {
        if (!file.isFile) {
            return CanonicalCsvInspection(
                canonical = false,
                sourceHeaderValid = false,
                dataRecordCount = 0,
                firstDataRecord = null,
                lastDataRecord = null,
                identityValue = null,
                identityConsistent = false,
                issue = "missing ${file.name}",
            )
        }

        val temporary = File(file.parentFile, ".${file.name}.recovery.tmp")
        val output = FileOutputStream(temporary)
        val writer = BufferedWriter(OutputStreamWriter(output, StandardCharsets.UTF_8))
        val inspection = try {
            canonicalScan(
                file = file,
                expectedHeader = expectedHeader,
                identityColumnIndex = identityColumnIndex,
                repaired = false,
                quarantinedOriginal = null,
                canonicalWriter = writer,
            )
        } finally {
            writer.flush()
            output.fd.sync()
            writer.close()
        }

        if (inspection.canonical) {
            temporary.delete()
            return inspection
        }

        // A malformed header cannot be interpreted. Leave a canonical header-only placeholder,
        // retain the source in quarantine, and let recovery metadata keep the session ineligible.
        if (!inspection.sourceHeaderValid) {
            FileOutputStream(temporary).use { replacementOutput ->
                BufferedWriter(OutputStreamWriter(replacementOutput, StandardCharsets.UTF_8)).use {
                    it.append(row(*expectedHeader.toTypedArray()))
                    it.newLine()
                    it.flush()
                    replacementOutput.fd.sync()
                }
            }
        }

        val quarantined = quarantineCopy(file, recoveryEpochMs)
        atomicReplace(temporary, file)
        return inspection.copy(
            canonical = true,
            repaired = true,
            quarantinedOriginal = quarantined,
        )
    }

    internal fun quarantineCopy(file: File, recoveryEpochMs: Long): File? {
        if (!file.isFile) return null
        val quarantineDirectory = File(file.parentFile, QUARANTINE_DIRECTORY)
        check(quarantineDirectory.isDirectory || quarantineDirectory.mkdirs()) {
            "Unable to create recovery quarantine"
        }
        var candidate = File(quarantineDirectory, "${file.name}.$recoveryEpochMs.corrupt")
        var collision = 1
        while (candidate.exists()) {
            candidate = File(
                quarantineDirectory,
                "${file.name}.$recoveryEpochMs.$collision.corrupt",
            )
            collision++
        }
        val temporary = File(quarantineDirectory, ".${candidate.name}.tmp")
        FileInputStream(file).use { input ->
            FileOutputStream(temporary).use { output ->
                input.copyTo(output)
                output.fd.sync()
            }
        }
        atomicReplace(temporary, candidate)
        return candidate
    }

    private fun canonicalScan(
        file: File,
        expectedHeader: List<String>,
        identityColumnIndex: Int,
        repaired: Boolean,
        quarantinedOriginal: File?,
        canonicalWriter: BufferedWriter?,
    ): CanonicalCsvInspection {
        if (!file.isFile) {
            return CanonicalCsvInspection(
                canonical = false,
                sourceHeaderValid = false,
                dataRecordCount = 0,
                firstDataRecord = null,
                lastDataRecord = null,
                identityValue = null,
                identityConsistent = false,
                issue = "missing ${file.name}",
                repaired = repaired,
                quarantinedOriginal = quarantinedOriginal,
            )
        }

        var headerSeen = false
        var headerValid = false
        var dataCount = 0L
        var firstData: List<String>? = null
        var lastData: List<String>? = null
        var identity: String? = null
        var identityConsistent = true
        var validationIssue: String? = null

        val parseIssue = scanRecords(file) { record ->
            if (!headerSeen) {
                headerSeen = true
                headerValid = record == expectedHeader
                if (!headerValid) {
                    validationIssue = "non-canonical ${file.name} header"
                    return@scanRecords false
                }
                canonicalWriter?.append(row(*expectedHeader.toTypedArray()))
                canonicalWriter?.newLine()
                return@scanRecords true
            }
            if (record.size != expectedHeader.size) {
                validationIssue =
                    "${file.name} record ${dataCount + 2} has ${record.size} columns; " +
                        "expected ${expectedHeader.size}"
                return@scanRecords false
            }
            if (firstData == null) firstData = record.toList()
            lastData = record.toList()
            dataCount++
            val recordIdentity = record[identityColumnIndex]
            if (identity == null) identity = recordIdentity else if (identity != recordIdentity) {
                identityConsistent = false
            }
            canonicalWriter?.append(row(*record.toTypedArray()))
            canonicalWriter?.newLine()
            true
        }

        val issue = validationIssue ?: parseIssue ?: when {
            !headerSeen -> "empty ${file.name}"
            !headerValid -> "non-canonical ${file.name} header"
            else -> null
        }
        return CanonicalCsvInspection(
            canonical = issue == null,
            sourceHeaderValid = headerValid,
            dataRecordCount = dataCount,
            firstDataRecord = firstData,
            lastDataRecord = lastData,
            identityValue = identity,
            identityConsistent = identityConsistent,
            issue = issue,
            repaired = repaired,
            quarantinedOriginal = quarantinedOriginal,
        )
    }

    /** Return a parse error, or null after consuming every complete record. */
    private fun scanRecords(
        file: File,
        onRecord: (List<String>) -> Boolean,
    ): String? {
        val fields = mutableListOf<String>()
        val field = StringBuilder()
        var state = ParserState.UNQUOTED
        var recordStarted = false
        var recordNumber = 1L

        fun emitRecord(): Boolean {
            fields += field.toString()
            field.setLength(0)
            val record = fields.toList()
            fields.clear()
            recordStarted = false
            state = ParserState.UNQUOTED
            val keepGoing = onRecord(record)
            recordNumber++
            return keepGoing
        }

        PushbackReader(file.reader(StandardCharsets.UTF_8), 1).use { reader ->
            while (true) {
                val value = reader.read()
                if (value == -1) break
                val character = value.toChar()
                when (state) {
                    ParserState.QUOTED -> when (character) {
                        '"' -> state = ParserState.AFTER_QUOTE
                        else -> field.append(character)
                    }
                    ParserState.AFTER_QUOTE -> when (character) {
                        '"' -> {
                            field.append('"')
                            state = ParserState.QUOTED
                        }
                        ',' -> {
                            fields += field.toString()
                            field.setLength(0)
                            state = ParserState.UNQUOTED
                            recordStarted = true
                        }
                        '\n' -> if (!emitRecord()) return null
                        '\r' -> {
                            val next = reader.read()
                            if (next != -1 && next.toChar() != '\n') reader.unread(next)
                            if (!emitRecord()) return null
                        }
                        else -> return "CSV syntax error after closing quote in record $recordNumber"
                    }
                    ParserState.UNQUOTED -> when (character) {
                        '"' -> {
                            if (field.isNotEmpty()) {
                                return "CSV quote inside unquoted field in record $recordNumber"
                            }
                            state = ParserState.QUOTED
                            recordStarted = true
                        }
                        ',' -> {
                            fields += field.toString()
                            field.setLength(0)
                            recordStarted = true
                        }
                        '\n' -> if (!emitRecord()) return null
                        '\r' -> {
                            val next = reader.read()
                            if (next != -1 && next.toChar() != '\n') reader.unread(next)
                            if (!emitRecord()) return null
                        }
                        else -> {
                            field.append(character)
                            recordStarted = true
                        }
                    }
                }
            }
        }

        if (state == ParserState.QUOTED) return "truncated quoted CSV record $recordNumber"
        if (
            recordStarted ||
            fields.isNotEmpty() ||
            field.isNotEmpty() ||
            state == ParserState.AFTER_QUOTE
        ) {
            return "unterminated CSV record $recordNumber"
        }
        return null
    }

    private fun atomicReplace(temporary: File, destination: File) {
        try {
            Files.move(
                temporary.toPath(),
                destination.toPath(),
                StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING,
            )
        } catch (_: AtomicMoveNotSupportedException) {
            Files.move(
                temporary.toPath(),
                destination.toPath(),
                StandardCopyOption.REPLACE_EXISTING,
            )
        }
    }

    internal const val QUARANTINE_DIRECTORY = ".recovery-quarantine"
}
