package com.luxiaoshi.simpletxtsearch

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

object SearchStore {
    private const val PREFS = "search_state"
    private const val KEY_RUNNING = "running"
    private const val KEY_STATUS = "status"
    private const val KEY_KEYWORD = "keyword"
    private const val KEY_SCANNED = "scanned"
    private const val KEY_MATCHED = "matched"
    private const val KEY_FAILED = "failed"
    private const val KEY_RESULTS = "results"

    data class Result(
        val name: String,
        val uri: String,
        val relativePath: String
    )

    data class Snapshot(
        val running: Boolean,
        val status: String,
        val keyword: String,
        val scanned: Int,
        val matched: Int,
        val failed: Int,
        val results: List<Result>
    )

    @Synchronized
    fun reset(context: Context, keyword: String) {
        prefs(context).edit()
            .putBoolean(KEY_RUNNING, true)
            .putString(KEY_STATUS, "正在准备搜索……")
            .putString(KEY_KEYWORD, keyword)
            .putInt(KEY_SCANNED, 0)
            .putInt(KEY_MATCHED, 0)
            .putInt(KEY_FAILED, 0)
            .putString(KEY_RESULTS, "[]")
            .apply()
    }

    @Synchronized
    fun updateProgress(
        context: Context,
        status: String,
        scanned: Int,
        matched: Int,
        failed: Int
    ) {
        prefs(context).edit()
            .putBoolean(KEY_RUNNING, true)
            .putString(KEY_STATUS, status)
            .putInt(KEY_SCANNED, scanned)
            .putInt(KEY_MATCHED, matched)
            .putInt(KEY_FAILED, failed)
            .apply()
    }

    @Synchronized
    fun appendResult(context: Context, result: Result) {
        val current = runCatching {
            JSONArray(prefs(context).getString(KEY_RESULTS, "[]") ?: "[]")
        }.getOrElse { JSONArray() }
        current.put(
            JSONObject()
                .put("name", result.name)
                .put("uri", result.uri)
                .put("relativePath", result.relativePath)
        )
        prefs(context).edit().putString(KEY_RESULTS, current.toString()).apply()
    }

    @Synchronized
    fun finish(
        context: Context,
        status: String,
        scanned: Int,
        matched: Int,
        failed: Int
    ) {
        prefs(context).edit()
            .putBoolean(KEY_RUNNING, false)
            .putString(KEY_STATUS, status)
            .putInt(KEY_SCANNED, scanned)
            .putInt(KEY_MATCHED, matched)
            .putInt(KEY_FAILED, failed)
            .apply()
    }

    fun snapshot(context: Context): Snapshot {
        val prefs = prefs(context)
        val results = mutableListOf<Result>()
        val array = runCatching {
            JSONArray(prefs.getString(KEY_RESULTS, "[]") ?: "[]")
        }.getOrElse { JSONArray() }
        for (index in 0 until array.length()) {
            val item = array.optJSONObject(index) ?: continue
            results += Result(
                name = item.optString("name"),
                uri = item.optString("uri"),
                relativePath = item.optString("relativePath")
            )
        }
        return Snapshot(
            running = prefs.getBoolean(KEY_RUNNING, false),
            status = prefs.getString(KEY_STATUS, "尚未开始搜索") ?: "尚未开始搜索",
            keyword = prefs.getString(KEY_KEYWORD, "") ?: "",
            scanned = prefs.getInt(KEY_SCANNED, 0),
            matched = prefs.getInt(KEY_MATCHED, 0),
            failed = prefs.getInt(KEY_FAILED, 0),
            results = results
        )
    }

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
