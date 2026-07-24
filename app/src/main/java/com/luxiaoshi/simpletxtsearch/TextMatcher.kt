package com.luxiaoshi.simpletxtsearch

import java.io.Reader
import java.util.Locale

object TextMatcher {
    fun contains(
        reader: Reader,
        keyword: String,
        caseSensitive: Boolean,
        isCancelled: () -> Boolean = { false }
    ): Boolean {
        if (keyword.isEmpty()) return false

        val normalizedKeyword = normalize(keyword, caseSensitive)
        val buffer = CharArray(DEFAULT_BUFFER_SIZE)
        var tail = ""

        while (!isCancelled()) {
            val count = reader.read(buffer)
            if (count < 0) return false
            if (count == 0) continue

            val chunk = tail + String(buffer, 0, count)
            if (normalize(chunk, caseSensitive).contains(normalizedKeyword)) {
                return true
            }

            val overlap = (keyword.length - 1).coerceAtLeast(0)
            tail = if (overlap == 0) "" else chunk.takeLast(overlap.coerceAtMost(chunk.length))
        }
        return false
    }

    private fun normalize(value: String, caseSensitive: Boolean): String {
        return if (caseSensitive) value else value.lowercase(Locale.ROOT)
    }

    private const val DEFAULT_BUFFER_SIZE = 8 * 1024
}
