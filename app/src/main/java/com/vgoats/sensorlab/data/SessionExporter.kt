package com.vgoats.sensorlab.data

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

object SessionExporter {
    fun share(context: Context, sessionDirectory: File) {
        val exportFiles = filesForExport(sessionDirectory)
        val exportDirectory = File(context.cacheDir, "exports").apply { mkdirs() }
        val zipFile = File(exportDirectory, "${sessionDirectory.name}.zip")
        val temporary = File(exportDirectory, ".${sessionDirectory.name}.zip.tmp")
        ZipOutputStream(FileOutputStream(temporary)).use { zip ->
            exportFiles.forEach { file ->
                zip.putNextEntry(ZipEntry(file.name))
                FileInputStream(file).use { it.copyTo(zip) }
                zip.closeEntry()
            }
        }
        atomicReplace(temporary, zipFile)
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", zipFile)
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "application/zip"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(intent, "Share sensor session"))
    }

    internal fun filesForExport(sessionDirectory: File): List<File> {
        val validation = SessionIntegrity.validateForExport(sessionDirectory)
        require(validation.valid) {
            "Session is not exportable: ${validation.reason ?: "integrity validation failed"}"
        }
        return validation.files.sortedBy { it.name }
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
