package com.luxiaoshi.simpletxtsearch

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SearchFileTypeTest {
    @Test
    fun classifiesSupportedExtensions() {
        assertEquals(SearchFileType.TXT, SearchFileType.fromFileName("小说.TXT"))
        assertEquals(SearchFileType.PDF, SearchFileType.fromFileName("报告.pdf"))
        assertEquals(SearchFileType.DOCUMENT, SearchFileType.fromFileName("材料.docx"))
        assertEquals(SearchFileType.DOCUMENT, SearchFileType.fromFileName("旧材料.doc"))
        assertEquals(SearchFileType.SPREADSHEET, SearchFileType.fromFileName("数据.xlsx"))
        assertEquals(SearchFileType.SPREADSHEET, SearchFileType.fromFileName("数据.ods"))
        assertNull(SearchFileType.fromFileName("图片.jpg"))
    }

    @Test
    fun defaultsToAllCategories() {
        assertEquals(SearchFileType.entries.toSet(), SearchFileType.parseNames(null))
        assertEquals(SearchFileType.entries.toSet(), SearchFileType.parseNames(emptySet()))
    }

    @Test
    fun chunkMatcherFindsKeywordAcrossChunks() {
        val matcher = ChunkMatcher("目标文字", true)
        assertFalse(matcher.feed("这里是目"))
        assertTrue(matcher.feed("标文字结尾"))
    }

    @Test
    fun chunkMatcherCanIgnoreCase() {
        val matcher = ChunkMatcher("txt search", false)
        assertFalse(matcher.feed("Simple TXT "))
        assertTrue(matcher.feed("Search"))
    }
}
