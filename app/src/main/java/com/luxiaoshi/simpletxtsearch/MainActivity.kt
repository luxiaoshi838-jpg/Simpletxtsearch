package com.luxiaoshi.simpletxtsearch

import android.Manifest
import android.content.BroadcastReceiver
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ListView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.documentfile.provider.DocumentFile
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {
    private data class FolderChoice(val name: String, val uri: String)

    private val prefs by lazy { getSharedPreferences("search_preferences", MODE_PRIVATE) }
    private var rootUri: Uri? = null
    private var folderChoices = emptyList<FolderChoice>()
    private var selectedFolderUris = mutableSetOf<String>()

    private lateinit var folderText: TextView
    private lateinit var rangeText: TextView
    private lateinit var keywordInput: EditText
    private lateinit var caseSensitiveCheck: CheckBox
    private lateinit var chooseRangeButton: Button
    private lateinit var startButton: Button
    private lateinit var stopButton: Button
    private lateinit var statusText: TextView
    private lateinit var resultHeader: TextView
    private lateinit var resultAdapter: ArrayAdapter<String>

    private val chooseFolder = registerForActivityResult(
        ActivityResultContracts.OpenDocumentTree()
    ) { uri ->
        if (uri != null) {
            runCatching {
                contentResolver.takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION
                )
            }
            rootUri = uri
            prefs.edit().putString(KEY_ROOT_URI, uri.toString()).apply()
            loadFolderChoices(showDialog = true, forceSelectAll = true)
        }
    }

    private val requestNotifications = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }

    private val progressReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            renderSnapshot()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(buildContentView())

        prefs.getString(KEY_ROOT_URI, null)?.let { saved ->
            rootUri = Uri.parse(saved)
            loadFolderChoices(showDialog = false, forceSelectAll = false)
        }
        renderSnapshot()
    }

    override fun onStart() {
        super.onStart()
        val filter = IntentFilter(SearchService.ACTION_PROGRESS)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(progressReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("DEPRECATION")
            registerReceiver(progressReceiver, filter)
        }
        renderSnapshot()
    }

    override fun onStop() {
        runCatching { unregisterReceiver(progressReceiver) }
        super.onStop()
    }

    private fun buildContentView(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(18), dp(18), dp(12))
            setBackgroundColor(Color.rgb(247, 245, 239))
        }

        root.addView(TextView(this).apply {
            text = "简搜"
            textSize = 28f
            setTextColor(Color.rgb(35, 67, 95))
        })
        root.addView(TextView(this).apply {
            text = "后台搜索指定文件夹中的 TXT，命中一次就搜索下一个文件"
            textSize = 14f
            setTextColor(Color.rgb(95, 95, 95))
            setPadding(0, dp(4), 0, dp(14))
        })

        val chooseFolderButton = Button(this).apply {
            text = "选择总文件夹"
            setOnClickListener { chooseFolder.launch(rootUri) }
        }
        root.addView(chooseFolderButton, matchWrap())

        folderText = TextView(this).apply {
            text = "尚未选择文件夹"
            textSize = 15f
            setTextColor(Color.rgb(45, 45, 45))
            setPadding(0, dp(8), 0, dp(4))
        }
        root.addView(folderText)

        chooseRangeButton = Button(this).apply {
            text = "选择参与搜索的子文件夹"
            isEnabled = false
            setOnClickListener { loadFolderChoices(showDialog = true, forceSelectAll = false) }
        }
        root.addView(chooseRangeButton, matchWrap())

        rangeText = TextView(this).apply {
            textSize = 14f
            setTextColor(Color.rgb(85, 85, 85))
            setPadding(0, dp(6), 0, dp(12))
        }
        root.addView(rangeText)

        keywordInput = EditText(this).apply {
            hint = "输入需要搜索的文字"
            textSize = 17f
            isSingleLine = true
        }
        root.addView(keywordInput, matchWrap())

        caseSensitiveCheck = CheckBox(this).apply {
            text = "区分大小写"
            isChecked = false
        }
        root.addView(caseSensitiveCheck)

        val actionRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        startButton = Button(this).apply {
            text = "开始后台搜索"
            setOnClickListener { startSearch() }
        }
        stopButton = Button(this).apply {
            text = "停止"
            setOnClickListener {
                startService(Intent(this@MainActivity, SearchService::class.java).setAction(SearchService.ACTION_STOP))
            }
        }
        actionRow.addView(startButton, weighted())
        actionRow.addView(stopButton, weighted())
        root.addView(actionRow, matchWrap())

        statusText = TextView(this).apply {
            textSize = 15f
            setTextColor(Color.rgb(50, 50, 50))
            setPadding(0, dp(10), 0, dp(8))
        }
        root.addView(statusText)

        val resultTitleRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        resultHeader = TextView(this).apply {
            textSize = 18f
            setTextColor(Color.rgb(35, 67, 95))
        }
        val copyButton = Button(this).apply {
            text = "复制文件名"
            setOnClickListener { copyResults() }
        }
        resultTitleRow.addView(resultHeader, weighted())
        resultTitleRow.addView(copyButton)
        root.addView(resultTitleRow, matchWrap())

        resultAdapter = ArrayAdapter(this, android.R.layout.simple_list_item_1, mutableListOf())
        val listView = ListView(this).apply {
            adapter = resultAdapter
            dividerHeight = 1
        }
        root.addView(listView, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            0,
            1f
        ))

        return root
    }

    private fun loadFolderChoices(showDialog: Boolean, forceSelectAll: Boolean) {
        val uri = rootUri ?: return
        lifecycleScope.launch {
            val rootDocument = withContext(Dispatchers.IO) {
                DocumentFile.fromTreeUri(this@MainActivity, uri)
            }
            if (rootDocument == null) {
                Toast.makeText(this@MainActivity, "无法读取所选文件夹", Toast.LENGTH_LONG).show()
                return@launch
            }
            val choices = withContext(Dispatchers.IO) {
                rootDocument.listFiles()
                    .filter { it.isDirectory }
                    .map { FolderChoice(it.name ?: "未命名文件夹", it.uri.toString()) }
                    .sortedBy { it.name.lowercase() }
            }
            folderChoices = choices
            folderText.text = "总文件夹：${rootDocument.name ?: uri.lastPathSegment ?: uri}"
            chooseRangeButton.isEnabled = choices.isNotEmpty()

            val sameRoot = prefs.getString(KEY_SELECTION_ROOT, null) == uri.toString()
            val saved = prefs.getStringSet(KEY_SELECTED_FOLDERS, emptySet()).orEmpty()
            selectedFolderUris = when {
                forceSelectAll -> choices.mapTo(mutableSetOf()) { it.uri }
                sameRoot -> choices.filter { it.uri in saved }.mapTo(mutableSetOf()) { it.uri }
                else -> choices.mapTo(mutableSetOf()) { it.uri }
            }
            saveFolderSelection()
            updateRangeSummary()

            if (showDialog) showFolderSelectionDialog()
        }
    }

    private fun showFolderSelectionDialog() {
        if (folderChoices.isEmpty()) {
            Toast.makeText(this, "该总文件夹下没有一级子文件夹，将只搜索根目录 TXT", Toast.LENGTH_LONG).show()
            return
        }
        val checked = BooleanArray(folderChoices.size) { index ->
            folderChoices[index].uri in selectedFolderUris
        }
        AlertDialog.Builder(this)
            .setTitle("选择参与搜索的子文件夹")
            .setMessage("默认全选。取消勾选后，该子文件夹及其所有下级文件夹都不会被搜索。根目录中的 TXT 始终参与搜索。")
            .setMultiChoiceItems(
                folderChoices.map { it.name }.toTypedArray(),
                checked
            ) { _, which, isChecked -> checked[which] = isChecked }
            .setNeutralButton("全选") { _, _ ->
                selectedFolderUris = folderChoices.mapTo(mutableSetOf()) { it.uri }
                saveFolderSelection()
                updateRangeSummary()
            }
            .setNegativeButton("取消", null)
            .setPositiveButton("确定") { _, _ ->
                selectedFolderUris = folderChoices.indices
                    .filter { checked[it] }
                    .mapTo(mutableSetOf()) { folderChoices[it].uri }
                saveFolderSelection()
                updateRangeSummary()
            }
            .show()
    }

    private fun saveFolderSelection() {
        prefs.edit()
            .putString(KEY_SELECTION_ROOT, rootUri?.toString())
            .putStringSet(KEY_SELECTED_FOLDERS, selectedFolderUris.toSet())
            .apply()
    }

    private fun updateRangeSummary() {
        rangeText.text = if (folderChoices.isEmpty()) {
            "搜索范围：根目录中的 TXT"
        } else {
            val excluded = folderChoices.size - selectedFolderUris.size
            "搜索范围：根目录 TXT + 已选 ${selectedFolderUris.size}/${folderChoices.size} 个一级子文件夹" +
                if (excluded > 0) "（已排除 $excluded 个）" else ""
        }
    }

    private fun startSearch() {
        val uri = rootUri
        val keyword = keywordInput.text.toString()
        if (uri == null) {
            Toast.makeText(this, "请先选择总文件夹", Toast.LENGTH_SHORT).show()
            return
        }
        if (keyword.isEmpty()) {
            Toast.makeText(this, "请输入需要搜索的文字", Toast.LENGTH_SHORT).show()
            return
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        }

        val intent = Intent(this, SearchService::class.java)
            .setAction(SearchService.ACTION_START)
            .putExtra(SearchService.EXTRA_ROOT_URI, uri.toString())
            .putExtra(SearchService.EXTRA_KEYWORD, keyword)
            .putStringArrayListExtra(
                SearchService.EXTRA_SELECTED_CHILDREN,
                ArrayList(selectedFolderUris)
            )
            .putExtra(SearchService.EXTRA_CASE_SENSITIVE, caseSensitiveCheck.isChecked)
        ContextCompat.startForegroundService(this, intent)
        Toast.makeText(this, "搜索已开始，可切换到其他软件或锁屏", Toast.LENGTH_LONG).show()
        renderSnapshot()
    }

    private fun renderSnapshot() {
        val snapshot = SearchStore.snapshot(this)
        statusText.text = snapshot.status
        resultHeader.text = "匹配文件（${snapshot.results.size}）"
        resultAdapter.clear()
        resultAdapter.addAll(snapshot.results.map { it.name })
        resultAdapter.notifyDataSetChanged()
        startButton.isEnabled = !snapshot.running
        stopButton.isEnabled = snapshot.running
        if (keywordInput.text.isEmpty() && snapshot.keyword.isNotEmpty()) {
            keywordInput.setText(snapshot.keyword)
        }
    }

    private fun copyResults() {
        val names = SearchStore.snapshot(this).results.map { it.name }
        if (names.isEmpty()) {
            Toast.makeText(this, "当前没有匹配文件", Toast.LENGTH_SHORT).show()
            return
        }
        val clipboard = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("简搜结果", names.joinToString("\n")))
        Toast.makeText(this, "已复制 ${names.size} 个文件名", Toast.LENGTH_SHORT).show()
    }

    private fun matchWrap() = LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT
    )

    private fun weighted() = LinearLayout.LayoutParams(
        0,
        LinearLayout.LayoutParams.WRAP_CONTENT,
        1f
    ).apply { setMargins(dp(3), 0, dp(3), 0) }

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()

    companion object {
        private const val KEY_ROOT_URI = "rootUri"
        private const val KEY_SELECTION_ROOT = "selectionRoot"
        private const val KEY_SELECTED_FOLDERS = "selectedFolders"
    }
}
