package com.vgoats.sensorlab.data

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.os.Environment
import android.provider.MediaStore
import androidx.core.content.FileProvider
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.OutputStream
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

object SessionExporter {
    fun share(context: Context, sessionDirectory: File) {
        val exportDirectory = File(context.cacheDir, "exports").apply { mkdirs() }
        val zipFile = writeZipFile(sessionDirectory, exportDirectory)
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", zipFile)
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "application/zip"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(intent, "Share sensor session"))
    }

    fun saveToDownloads(context: Context, sessionDirectory: File): String {
        val displayName = "${sessionDirectory.name}.zip"
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, displayName)
            put(MediaStore.Downloads.MIME_TYPE, "application/zip")
            put(
                MediaStore.Downloads.RELATIVE_PATH,
                "${Environment.DIRECTORY_DOWNLOADS}/GoatSensorLab",
            )
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val resolver = context.contentResolver
        val uri = requireNotNull(
            resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values),
        ) {
            "Unable to create Downloads export"
        }
        try {
            resolver.openOutputStream(uri, "w").use { output ->
                requireNotNull(output) { "Unable to open Downloads export" }
                writeZip(sessionDirectory, output)
            }
            values.clear()
            values.put(MediaStore.Downloads.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
            return "Download/GoatSensorLab/$displayName"
        } catch (error: Throwable) {
            resolver.delete(uri, null, null)
            throw error
        }
    }

    internal fun filesForExport(sessionDirectory: File): List<File> {
        val validation = SessionIntegrity.validateForExport(sessionDirectory)
        require(validation.valid) {
            "Session is not exportable: ${validation.reason ?: "integrity validation failed"}"
        }
        return validation.files.sortedBy { it.name }
    }

    private fun writeZipFile(sessionDirectory: File, exportDirectory: File): File {
        val zipFile = File(exportDirectory, "${sessionDirectory.name}.zip")
        val temporary = File(exportDirectory, ".${sessionDirectory.name}.zip.tmp")
        FileOutputStream(temporary).use { output -> writeZip(sessionDirectory, output) }
        atomicReplace(temporary, zipFile)
        return zipFile
    }

    private fun writeZip(sessionDirectory: File, output: OutputStream) {
        val exportFiles = filesForExport(sessionDirectory)
        ZipOutputStream(output).use { zip ->
            exportFiles.forEach { file ->
                zip.putNextEntry(ZipEntry(file.name))
                FileInputStream(file).use { it.copyTo(zip) }
                zip.closeEntry()
            }
        }
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
}
