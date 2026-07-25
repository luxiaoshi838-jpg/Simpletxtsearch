package com.luxiaoshi.simpletxtsearch

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MultiKeywordMatcherTest {
    @Test
    fun requiresEveryKeyword() {
        val matcher = MultiKeywordMatcher(listOf("甲", "乙", "丙"), true)
        assertFalse(matcher.feed("只有甲和乙"))
        assertTrue(matcher.feed("最后出现丙"))
    }

    @Test
    fun supportsKeywordsAcrossReadBoundaries() {
        val matcher = MultiKeywordMatcher(listOf("目标文字", "第二词"), true)
        assertFalse(matcher.feed("这里是目"))
        assertFalse(matcher.feed("标文字，后面还有第"))
        assertTrue(matcher.feed("二词"))
    }

    @Test
    fun supportsCaseInsensitiveMatching() {
        val matcher = MultiKeywordMatcher(listOf("simple", "SEARCH"), false)
        assertTrue(matcher.feed("Simple Txt Search"))
    }
}
