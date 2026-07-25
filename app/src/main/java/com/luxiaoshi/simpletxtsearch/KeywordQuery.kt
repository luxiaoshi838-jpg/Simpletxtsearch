package com.luxiaoshi.simpletxtsearch

object KeywordQuery {
    const val MAX_KEYWORDS = 10

    fun split(raw: String): List<String> =
        raw.trim()
            .split(Regex("\\s+"))
            .filter { it.isNotEmpty() }

    fun parse(raw: String): List<String> {
        val tokens = split(raw)
        require(tokens.size <= MAX_KEYWORDS) {
            "关键词最多 $MAX_KEYWORDS 个"
        }
        return tokens.distinct()
    }
}
