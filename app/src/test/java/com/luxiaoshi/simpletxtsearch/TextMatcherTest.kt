package com.luxiaoshi.simpletxtsearch

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.Reader
import java.io.StringReader

class TextMatcherTest {
    @Test
    fun findsNormalMatch() {
        assertTrue(TextMatcher.contains(StringReader("前文 目标文字 后文"), "目标文字", true))
    }

    @Test
    fun stopsAfterFirstMatchEvenAcrossReadBoundaries() {
        val reader = object : Reader() {
            private val chunks = listOf("这里是目", "标文字结尾")
            private var index = 0

            override fun read(cbuf: CharArray, off: Int, len: Int): Int {
                if (index >= chunks.size) return -1
                val chunk = chunks[index++]
                chunk.toCharArray().copyInto(cbuf, off)
                return chunk.length
            }

            override fun close() = Unit
        }
        assertTrue(TextMatcher.contains(reader, "目标文字", true))
    }

    @Test
    fun supportsCaseInsensitiveSearch() {
        assertTrue(TextMatcher.contains(StringReader("Simple TXT Search"), "txt search", false))
        assertFalse(TextMatcher.contains(StringReader("Simple TXT Search"), "txt search", true))
    }
}
