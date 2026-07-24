package com.luxiaoshi.simpletxtsearch

import java.util.Locale

class ChunkMatcher(keyword: String, private val caseSensitive: Boolean) {
    private val target = normalize(keyword)
    private val overlap = (keyword.length - 1).coerceAtLeast(0)
    private var tail = ""

    fun feed(value: String): Boolean {
        if (target.isEmpty()) return false
        val combined = tail + value
        if (normalize(combined).contains(target)) return true
        tail = if (overlap == 0) "" else combined.takeLast(overlap.coerceAtMost(combined.length))
        return false
    }

    fun separator(): Boolean = feed("\n")

    private fun normalize(value: String): String =
        if (caseSensitive) value else value.lowercase(Locale.ROOT)
}
