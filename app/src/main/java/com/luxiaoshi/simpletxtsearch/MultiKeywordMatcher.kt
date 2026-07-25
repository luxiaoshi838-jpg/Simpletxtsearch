package com.luxiaoshi.simpletxtsearch

import java.util.Locale

class MultiKeywordMatcher(
    keywords: List<String>,
    private val caseSensitive: Boolean
) {
    private val targets = keywords.map(::normalize)
    private val found = BooleanArray(targets.size)
    private val tails = Array(targets.size) { "" }
    private val overlaps = IntArray(targets.size) { index ->
        (targets[index].length - 1).coerceAtLeast(0)
    }

    val isComplete: Boolean
        get() = targets.isNotEmpty() && found.all { it }

    fun feed(value: String): Boolean {
        if (targets.isEmpty()) return false
        targets.indices.forEach { index ->
            if (found[index]) return@forEach
            val combined = tails[index] + value
            val normalized = normalize(combined)
            if (normalized.contains(targets[index])) {
                found[index] = true
                tails[index] = ""
            } else {
                val overlap = overlaps[index]
                tails[index] = if (overlap == 0) {
                    ""
                } else {
                    combined.takeLast(overlap.coerceAtMost(combined.length))
                }
            }
        }
        return isComplete
    }

    fun separator(): Boolean = feed("\n")

    private fun normalize(value: String): String =
        if (caseSensitive) value else value.lowercase(Locale.ROOT)
}
