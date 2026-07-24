package com.luxiaoshi.simpletxtsearch

import java.util.Locale

enum class SearchFileType(
    val label: String,
    val extensions: Set<String>
) {
    TXT("TXT", setOf("txt", "md", "log")),
    PDF("PDF", setOf("pdf")),
    DOCUMENT("文档", setOf("doc", "docx", "odt", "rtf")),
    SPREADSHEET("表格", setOf("xls", "xlsx", "ods", "csv", "tsv"));

    companion object {
        val defaultSelection: Set<SearchFileType> = entries.toSet()

        fun fromFileName(name: String?): SearchFileType? {
            val extension = name
                ?.substringAfterLast('.', missingDelimiterValue = "")
                ?.lowercase(Locale.ROOT)
                .orEmpty()
            return entries.firstOrNull { extension in it.extensions }
        }

        fun parseNames(names: Collection<String>?): Set<SearchFileType> {
            if (names.isNullOrEmpty()) return defaultSelection
            return names.mapNotNullTo(linkedSetOf()) { saved ->
                entries.firstOrNull { it.name == saved }
            }.ifEmpty { defaultSelection }
        }

        fun labels(types: Set<SearchFileType>): String {
            if (types.containsAll(defaultSelection)) return "全部"
            return entries.filter { it in types }.joinToString("、") { it.label }
        }
    }
}
