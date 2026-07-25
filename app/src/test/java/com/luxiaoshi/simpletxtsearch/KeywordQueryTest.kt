package com.luxiaoshi.simpletxtsearch

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class KeywordQueryTest {
    @Test
    fun splitsOnWhitespace() {
        assertEquals(listOf("甲", "乙", "丙"), KeywordQuery.parse(" 甲   乙\t丙 "))
    }

    @Test
    fun keepsAtMostTenKeywords() {
        assertEquals(10, KeywordQuery.parse((1..10).joinToString(" ")).size)
        assertThrows(IllegalArgumentException::class.java) {
            KeywordQuery.parse((1..11).joinToString(" "))
        }
    }
}
