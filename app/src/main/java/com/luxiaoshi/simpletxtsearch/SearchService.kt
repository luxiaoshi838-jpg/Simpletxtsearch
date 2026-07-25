package com.luxiaoshi.simpletxtsearch

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import androidx.documentfile.provider.DocumentFile
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean

class SearchService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var searchJob: Job? = null
    private val stopRequested = AtomicBoolean(false)
    private var wakeLock: PowerManager.WakeLock? = null

    private var scanned = 0
    private var matched = 0
    private var failed = 0
    private var lastNotificationAt = 0L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> stopSearch("搜索已停止")
            ACTION_START -> startSearch(intent)
        }
        return START_REDELIVER_INTENT
    }

    private fun startSearch(intent: Intent) {
        searchJob?.cancel()
        stopRequested.set(false)
        scanned = 0
        matched = 0
        failed = 0

        val rootUri = intent.getStringExtra(EXTRA_ROOT_URI)
        val rawKeyword = intent.getStringExtra(EXTRA_KEYWORD).orEmpty()
        val keywordTokens = KeywordQuery.split(rawKeyword)
        val selectedChildren = intent.getStringArrayListExtra(EXTRA_SELECTED_CHILDREN)
            ?.toSet().orEmpty()
        val selectedTypes = SearchFileType.parseNames(
            intent.getStringArrayListExtra(EXTRA_SELECTED_FILE_TYPES)
        )
        val caseSensitive = intent.getBooleanExtra(EXTRA_CASE_SENSITIVE, false)

        val parameterError = when {
            rootUri.isNullOrBlank() -> "请先选择总文件夹"
            keywordTokens.isEmpty() -> "请输入至少 1 个关键词"
            keywordTokens.size > KeywordQuery.MAX_KEYWORDS -> "关键词最多 ${KeywordQuery.MAX_KEYWORDS} 个，请用空格分隔"
            selectedTypes.isEmpty() -> "请至少选择一种文件类型"
            else -> null
        }
        if (parameterError != null) {
            SearchStore.finish(this, parameterError, 0, 0, 0)
            broadcastProgress()
            stopSelf()
            return
        }
        val keywords = keywordTokens.distinct()

        SearchStore.reset(this, rawKeyword.trim())
        startForeground(NOTIFICATION_ID, buildNotification("正在准备搜索……"))
        acquireWakeLock()

        searchJob = scope.launch {
            try {
                val root = DocumentFile.fromTreeUri(this@SearchService, Uri.parse(rootUri))
                    ?: error("无法读取所选文件夹")
                val children = root.listFiles().sortedBy { it.name?.lowercase(Locale.ROOT).orEmpty() }

                children.filter { it.isFile }
                    .forEach { file ->
                        SearchFileType.fromFileName(file.name)
                            ?.takeIf { it in selectedTypes }
                            ?.let { type -> scanFile(file, file.name.orEmpty(), type, keywords, caseSensitive) }
                    }

                children.filter { it.isDirectory && it.uri.toString() in selectedChildren }
                    .forEach { directory ->
                        scanDirectory(
                            directory = directory,
                            relativePath = directory.name.orEmpty(),
                            selectedTypes = selectedTypes,
                            keywords = keywords,
                            caseSensitive = caseSensitive
                        )
                    }

                val status = buildString {
                    append("搜索完成：已扫描 ")
                    append(scanned)
                    append(" 个文件，找到 ")
                    append(matched)
                    append(" 个文件")
                    if (failed > 0) append("，跳过 $failed 个无法读取的文件")
                }
                SearchStore.finish(this@SearchService, status, scanned, matched, failed)
                broadcastProgress()
                showFinishedNotification(status)
            } catch (_: CancellationException) {
                if (stopRequested.get()) {
                    SearchStore.finish(this@SearchService, "搜索已停止", scanned, matched, failed)
                    broadcastProgress()
                }
            } catch (error: Throwable) {
                val status = "搜索失败：${error.message ?: error.javaClass.simpleName}"
                SearchStore.finish(this@SearchService, status, scanned, matched, failed)
                broadcastProgress()
                showFinishedNotification(status)
            } finally {
                releaseWakeLock()
                stopForeground(false)
                stopSelf()
            }
        }
    }

    private suspend fun scanDirectory(
        directory: DocumentFile,
        relativePath: String,
        selectedTypes: Set<SearchFileType>,
        keywords: List<String>,
        caseSensitive: Boolean
    ) {
        if (!scope.isActive || stopRequested.get()) throw CancellationException()
        directory.listFiles()
            .sortedBy { it.name?.lowercase(Locale.ROOT).orEmpty() }
            .forEach { child ->
                if (stopRequested.get()) throw CancellationException()
                val childPath = if (relativePath.isBlank()) {
                    child.name.orEmpty()
                } else {
                    "$relativePath/${child.name.orEmpty()}"
                }
                when {
                    child.isDirectory -> scanDirectory(
                        child,
                        childPath,
                        selectedTypes,
                        keywords,
                        caseSensitive
                    )
                    child.isFile -> SearchFileType.fromFileName(child.name)
                        ?.takeIf { it in selectedTypes }
                        ?.let { type -> scanFile(child, childPath, type, keywords, caseSensitive) }
                }
            }
    }

    private fun scanFile(
        file: DocumentFile,
        relativePath: String,
        type: SearchFileType,
        keywords: List<String>,
        caseSensitive: Boolean
    ) {
        if (stopRequested.get()) throw CancellationException()
        val hit = runCatching {
            ContentSearchEngine.contains(
                context = this,
                uri = file.uri,
                fileName = file.name.orEmpty(),
                keywords = keywords,
                caseSensitive = caseSensitive,
                isCancelled = { stopRequested.get() || !scope.isActive }
            )
        }.onFailure { error ->
            if (error is CancellationException) throw error
            failed += 1
        }.getOrDefault(false)

        scanned += 1
        if (hit) {
            matched += 1
            SearchStore.appendResult(
                this,
                SearchStore.Result(
                    name = file.name ?: "未命名文件",
                    uri = file.uri.toString(),
                    relativePath = relativePath
                )
            )
        }

        val status = "正在搜索：已扫描 $scanned 个，找到 $matched 个 · ${type.label}"
        SearchStore.updateProgress(this, status, scanned, matched, failed)
        val now = System.currentTimeMillis()
        if (hit || scanned % 3 == 0 || now - lastNotificationAt >= 750L) {
            lastNotificationAt = now
            updateNotification(status)
            broadcastProgress()
        }
    }

    private fun stopSearch(status: String) {
        stopRequested.set(true)
        searchJob?.cancel()
        SearchStore.finish(this, status, scanned, matched, failed)
        broadcastProgress()
        releaseWakeLock()
        stopForeground(true)
        stopSelf()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "文件内容搜索任务",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "显示简搜后台扫描进度"
            }
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun buildNotification(text: String) = NotificationCompat.Builder(this, CHANNEL_ID)
        .setSmallIcon(android.R.drawable.ic_menu_search)
        .setContentTitle("简搜正在后台运行")
        .setContentText(text)
        .setOnlyAlertOnce(true)
        .setOngoing(true)
        .setContentIntent(openAppPendingIntent())
        .addAction(
            android.R.drawable.ic_menu_close_clear_cancel,
            "停止",
            stopPendingIntent()
        )
        .build()

    private fun updateNotification(text: String) {
        getSystemService(NotificationManager::class.java)
            .notify(NOTIFICATION_ID, buildNotification(text))
    }

    private fun showFinishedNotification(text: String) {
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_search)
            .setContentTitle("简搜任务结束")
            .setContentText(text)
            .setAutoCancel(true)
            .setContentIntent(openAppPendingIntent())
            .build()
        getSystemService(NotificationManager::class.java)
            .notify(NOTIFICATION_ID, notification)
    }

    private fun openAppPendingIntent(): PendingIntent {
        val intent = Intent(this, MainActivity::class.java)
        return PendingIntent.getActivity(
            this,
            1,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    private fun stopPendingIntent(): PendingIntent {
        val intent = Intent(this, SearchService::class.java).setAction(ACTION_STOP)
        return PendingIntent.getService(
            this,
            2,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    private fun broadcastProgress() {
        sendBroadcast(
            Intent(ACTION_PROGRESS)
                .setPackage(packageName)
        )
    }

    private fun acquireWakeLock() {
        releaseWakeLock()
        val manager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = manager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "$packageName:file-search"
        ).apply {
            setReferenceCounted(false)
            acquire(6 * 60 * 60 * 1000L)
        }
    }

    private fun releaseWakeLock() {
        wakeLock?.let { lock ->
            if (lock.isHeld) lock.release()
        }
        wakeLock = null
    }

    override fun onTimeout(startId: Int, fgsType: Int) {
        stopSearch("系统后台运行时限已到，请重新开始搜索")
    }

    override fun onDestroy() {
        releaseWakeLock()
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        const val ACTION_START = "com.luxiaoshi.simpletxtsearch.START"
        const val ACTION_STOP = "com.luxiaoshi.simpletxtsearch.STOP"
        const val ACTION_PROGRESS = "com.luxiaoshi.simpletxtsearch.PROGRESS"

        const val EXTRA_ROOT_URI = "rootUri"
        const val EXTRA_KEYWORD = "keyword"
        const val EXTRA_SELECTED_CHILDREN = "selectedChildren"
        const val EXTRA_SELECTED_FILE_TYPES = "selectedFileTypes"
        const val EXTRA_CASE_SENSITIVE = "caseSensitive"

        private const val CHANNEL_ID = "file_content_search"
        private const val NOTIFICATION_ID = 2407
    }
}
