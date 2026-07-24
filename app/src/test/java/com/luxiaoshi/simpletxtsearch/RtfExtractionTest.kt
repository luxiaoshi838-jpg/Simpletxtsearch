package com.luxiaoshi.simpletxtsearch

import org.junit.Assert.assertTrue
import org.junit.Test

class RtfExtractionTest {
    @Test
    fun extractsPlainAndUnicodeText() {
        val text = ContentSearchEngine.extractRtfText("{\\rtf1 普通文字 \\u30446?目标}")
        assertTrue(text.contains("普通文字"))
        assertTrue(text.contains("目标"))
    }
}
