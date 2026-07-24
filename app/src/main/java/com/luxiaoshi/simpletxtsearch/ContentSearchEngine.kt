package com.luxiaoshi.simpletxtsearch

import android.content.Context
import android.net.Uri
import android.util.Xml
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.text.PDFTextStripper
import kotlinx.coroutines.CancellationException
import org.apache.poi.hssf.usermodel.HSSFWorkbook
import org.apache.poi.hwpf.HWPFDocument
import org.apache.poi.hwpf.extractor.WordExtractor
import org.apache.poi.ss.usermodel.DataFormatter
import org.mozilla.universalchardet.UniversalDetector
import org.xmlpull.v1.XmlPullParser
import java.io.BufferedInputStream
import java.io.ByteArrayInputStream
import java.io.InputStream
import java.io.InputStreamReader
import java.nio.charset.Charset
import java.nio.charset.StandardCharsets
import java.util.Locale
import java.util.zip.ZipInputStream

object ContentSearchEngine {
    fun contains(
        context: Context,
        uri: Uri,
        fileName: String,
        keyword: String,
        caseSensitive: Boolean,
        isCancelled: () -> Boolean
    ): Boolean {
        checkCancelled(isCancelled)
        val extension = fileName.substringAfterLast('.', "").lowercase(Locale.ROOT)
        return when (extension) {
            "txt", "md", "log", "csv", "tsv" -> containsPlainText(
                context,
                uri,
                keyword,
                caseSensitive,
                isCancelled
            )
            "pdf" -> containsPdf(context, uri, keyword, caseSensitive, isCancelled)
            "doc" -> containsLegacyWord(context, uri, keyword, caseSensitive, isCancelled)
            "xls" -> containsLegacySpreadsheet(context, uri, keyword, caseSensitive, isCancelled)
            "docx", "xlsx", "odt", "ods" -> containsZipXml(
                context,
                uri,
                extension,
                keyword,
                caseSensitive,
                isCancelled
            )
            "rtf" -> containsRtf(context, uri, keyword, caseSensitive, isCancelled)
            else -> false
        }
    }

    private fun containsPlainText(
        context: Context,
        uri: Uri,
        keyword: String,
        caseSensitive: Boolean,
        isCancelled: () -> Boolean
    ): Boolean {
        val charset = detectCharset(context, uri)
        return context.contentResolver.openInputStream(uri)?.use { input ->
            InputStreamReader(input, charset).use { reader ->
                TextMatcher.contains(reader, keyword, caseSensitive, isCancelled)
            }
        } ?: false
    }

    private fun containsPdf(
        context: Context,
        uri: Uri,
        keyword: String,
        caseSensitive: Boolean,
        isCancelled: () -> Boolean
    ): Boolean {
        return context.contentResolver.openInputStream(uri)?.use { input ->
            PDDocument.load(input).use { document ->
                val stripper = PDFTextStripper()
                for (page in 1..document.numberOfPages) {
                    checkCancelled(isCancelled)
                    stripper.startPage = page
                    stripper.endPage = page
                    if (matches(stripper.getText(document), keyword, caseSensitive)) return true
                }
                false
            }
        } ?: false
    }

    private fun containsLegacyWord(
        context: Context,
        uri: Uri,
        keyword: String,
        caseSensitive: Boolean,
        isCancelled: () -> Boolean
    ): Boolean {
        return context.contentResolver.openInputStream(uri)?.use { input ->
            checkCancelled(isCancelled)
            HWPFDocument(input).use { document ->
                WordExtractor(document).use { extractor ->
                    matches(extractor.text, keyword, caseSensitive)
                }
            }
        } ?: false
    }

    private fun containsLegacySpreadsheet(
        context: Context,
        uri: Uri,
        keyword: String,
        caseSensitive: Boolean,
        isCancelled: () -> Boolean
    ): Boolean {
        return context.contentResolver.openInputStream(uri)?.use { input ->
            HSSFWorkbook(input).use { workbook ->
                val formatter = DataFormatter()
                for (sheetIndex in 0 until workbook.numberOfSheets) {
                    checkCancelled(isCancelled)
                    val sheet = workbook.getSheetAt(sheetIndex)
                    if (matches(sheet.sheetName, keyword, caseSensitive)) return true
                    for (row in sheet) {
                        checkCancelled(isCancelled)
                        for (cell in row) {
                            if (matches(formatter.formatCellValue(cell), keyword, caseSensitive)) return true
                        }
                    }
                }
                false
            }
        } ?: false
    }

    private fun containsZipXml(
        context: Context,
        uri: Uri,
        extension: String,
        keyword: String,
        caseSensitive: Boolean,
        isCancelled: () -> Boolean
    ): Boolean {
        return context.contentResolver.openInputStream(uri)?.use { input ->
            ZipInputStream(BufferedInputStream(input)).use { zip ->
                var entry = zip.nextEntry
                while (entry != null) {
                    checkCancelled(isCancelled)
                    val name = entry.name.lowercase(Locale.ROOT)
                    if (!entry.isDirectory && isSearchableXmlEntry(extension, name)) {
                        if (containsXmlText(zip, keyword, caseSensitive, isCancelled)) return true
                    }
                    zip.closeEntry()
                    entry = zip.nextEntry
                }
                false
            }
        } ?: false
    }

    private fun containsXmlText(
        input: InputStream,
        keyword: String,
        caseSensitive: Boolean,
        isCancelled: () -> Boolean
    ): Boolean {
        val matcher = ChunkMatcher(keyword, caseSensitive)
        val parser = Xml.newPullParser()
        parser.setFeature(XmlPullParser.FEATURE_PROCESS_NAMESPACES, true)
        parser.setInput(input, null)
        var event = parser.eventType
        while (event != XmlPullParser.END_DOCUMENT) {
            checkCancelled(isCancelled)
            when (event) {
                XmlPullParser.TEXT, XmlPullParser.CDSECT -> {
                    if (matcher.feed(parser.text.orEmpty())) return true
                }
                XmlPullParser.END_TAG -> {
                    if (parser.name.lowercase(Locale.ROOT) in XML_BREAK_TAGS && matcher.separator()) {
                        return true
                    }
                }
            }
            event = parser.next()
        }
        return false
    }

    private fun isSearchableXmlEntry(extension: String, entryName: String): Boolean {
        return when (extension) {
            "docx" -> entryName == "word/document.xml" ||
                entryName.startsWith("word/header") ||
                entryName.startsWith("word/footer") ||
                entryName in setOf(
                    "word/footnotes.xml",
                    "word/endnotes.xml",
                    "word/comments.xml"
                )
            "xlsx" -> entryName == "xl/sharedstrings.xml" ||
                entryName.startsWith("xl/worksheets/") ||
                entryName.startsWith("xl/comments")
            "odt", "ods" -> entryName == "content.xml"
            else -> false
        }
    }

    private fun containsRtf(
        context: Context,
        uri: Uri,
        keyword: String,
        caseSensitive: Boolean,
        isCancelled: () -> Boolean
    ): Boolean {
        val raw = context.contentResolver.openInputStream(uri)?.use { input ->
            InputStreamReader(input, Charset.forName("windows-1252")).readText()
        } ?: return false
        checkCancelled(isCancelled)
        return matches(extractRtfText(raw, isCancelled), keyword, caseSensitive)
    }

    internal fun extractRtfText(raw: String, isCancelled: () -> Boolean = { false }): String {
        val output = StringBuilder(raw.length.coerceAtMost(1024 * 1024))
        val skipStack = ArrayDeque<Boolean>()
        var skip = false
        var index = 0
        var pendingDestination = false
        while (index < raw.length) {
            if (index % 4096 == 0) checkCancelled(isCancelled)
            when (val char = raw[index]) {
                '{' -> {
                    skipStack.addLast(skip)
                    index += 1
                }
                '}' -> {
                    skip = if (skipStack.isEmpty()) false else skipStack.removeLast()
                    pendingDestination = false
                    index += 1
                }
                '\\' -> {
                    index += 1
                    if (index >= raw.length) break
                    when (raw[index]) {
                        '\\', '{', '}' -> {
                            if (!skip) output.append(raw[index])
                            index += 1
                        }
                        '*' -> {
                            pendingDestination = true
                            index += 1
                        }
                        '\'' -> {
                            if (index + 2 < raw.length) {
                                val hex = raw.substring(index + 1, index + 3)
                                val value = hex.toIntOrNull(16)
                                if (!skip && value != null) output.append(value.toChar())
                                index += 3
                            } else {
                                index = raw.length
                            }
                        }
                        else -> {
                            val wordStart = index
                            while (index < raw.length && raw[index].isLetter()) index += 1
                            val word = raw.substring(wordStart, index).lowercase(Locale.ROOT)
                            val numberStart = index
                            if (index < raw.length && (raw[index] == '-' || raw[index] == '+')) index += 1
                            while (index < raw.length && raw[index].isDigit()) index += 1
                            val number = raw.substring(numberStart, index).toIntOrNull()
                            if (index < raw.length && raw[index] == ' ') index += 1

                            if (pendingDestination || word in RTF_DESTINATIONS) {
                                skip = true
                                pendingDestination = false
                            } else if (!skip) {
                                when (word) {
                                    "par", "line" -> output.append('\n')
                                    "tab" -> output.append('\t')
                                    "u" -> {
                                        number?.let { code ->
                                            output.append((code and 0xFFFF).toChar())
                                            if (index < raw.length && raw[index] !in charArrayOf('\\', '{', '}')) {
                                                index += 1
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                '\r', '\n' -> index += 1
                else -> {
                    if (!skip) output.append(char)
                    index += 1
                }
            }
        }
        return output.toString()
    }

    private fun detectCharset(context: Context, uri: Uri): Charset {
        val sample = context.contentResolver.openInputStream(uri)?.use { input ->
            val buffer = ByteArray(64 * 1024)
            val size = input.read(buffer)
            if (size <= 0) ByteArray(0) else buffer.copyOf(size)
        } ?: ByteArray(0)

        if (sample.size >= 3 && sample[0] == 0xEF.toByte() && sample[1] == 0xBB.toByte() && sample[2] == 0xBF.toByte()) {
            return StandardCharsets.UTF_8
        }
        if (sample.size >= 2 && sample[0] == 0xFF.toByte() && sample[1] == 0xFE.toByte()) {
            return StandardCharsets.UTF_16LE
        }
        if (sample.size >= 2 && sample[0] == 0xFE.toByte() && sample[1] == 0xFF.toByte()) {
            return StandardCharsets.UTF_16BE
        }

        val detector = UniversalDetector(null)
        if (sample.isNotEmpty()) detector.handleData(sample, 0, sample.size)
        detector.dataEnd()
        val detected = detector.detectedCharset?.uppercase(Locale.ROOT)
        detector.reset()
        val normalized = when (detected) {
            "GB2312", "GBK", "GB18030" -> "GB18030"
            "UTF8" -> "UTF-8"
            else -> detected
        }
        return runCatching {
            if (normalized.isNullOrBlank()) StandardCharsets.UTF_8 else Charset.forName(normalized)
        }.getOrDefault(StandardCharsets.UTF_8)
    }

    private fun matches(text: String, keyword: String, caseSensitive: Boolean): Boolean {
        return if (caseSensitive) {
            text.contains(keyword)
        } else {
            text.contains(keyword, ignoreCase = true)
        }
    }

    private fun checkCancelled(isCancelled: () -> Boolean) {
        if (isCancelled()) throw CancellationException()
    }

    private val XML_BREAK_TAGS = setOf(
        "p", "br", "tr", "row", "c", "si", "t", "table-row", "table-cell"
    )

    private val RTF_DESTINATIONS = setOf(
        "fonttbl", "colortbl", "stylesheet", "info", "pict", "object", "header", "footer",
        "filetbl", "listtable", "listoverridetable", "generator", "xmlnstbl", "datastore"
    )
}
