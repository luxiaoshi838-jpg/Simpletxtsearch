package com.luxiaoshi.simpletxtsearch

import java.io.Reader

object TextMatcher {
    fun contains(
        reader: Reader,
        keyword: String,
        caseSensitive: Boolean,
        isCancelled: () -> Boolean = { false }
    ): Boolean = contains(reader, listOf(keyword), caseSensitive, isCancelled)

    fun contains(
        reader: Reader,
        keywords: List<String>,
        caseSensitive: Boolean,
        isCancelled: () -> Boolean = { false }
    ): Boolean {
        if (keywords.isEmpty()) return false

        val matcher = MultiKeywordMatcher(keywords, caseSensitive)
        val buffer = CharArray(DEFAULT_BUFFER_SIZE)

        while (!isCancelled()) {
            val count = reader.read(buffer)
            if (count < 0) return false
            if (count == 0) continue
            if (matcher.feed(String(buffer, 0, count))) return true
        }
        return false
    }

    private const val DEFAULT_BUFFER_SIZE = 8 * 1024
}
