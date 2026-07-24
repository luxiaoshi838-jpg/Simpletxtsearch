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
import androidx.core.widget.doAfterTextChanged
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
    private var selectedFileTypes = SearchFileType.defaultSelection.toMutableSet()

    private lateinit var folderText: TextView
    private lateinit var rangeText: TextView
    private lateinit var typeText: TextView
    private lateinit var keywordInput: EditText
    private lateinit var caseSensitiveCheck: CheckBox
    private lateinit var chooseRangeButton: Button
    private lateinit var chooseTypesButton: Button
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

        selectedFileTypes = SearchFileType.parseNames(
            prefs.getStringSet(KEY_SELECTED_TYPES, emptySet())
        ).toMutableSet()
        updateTypeSummary()

        val snapshot = SearchStore.snapshot(this)
        val savedKeyword = prefs.getString(KEY_KEYWORD, null)
            ?.takeIf { it.isNotEmpty() }
            ?: snapshot.keyword
        keywordInput.setText(savedKeyword)
        keywordInput.setSelection(keywordInput.text.length)
        caseSensitiveCheck.isChecked = prefs.getBoolean(KEY_CASE_SENSITIVE, false)

        keywordInput.doAfterTextChanged { value ->
            prefs.edit().putString(KEY_KEYWORD, value?.toString().orEmpty()).apply()
        }
        caseSensitiveCheck.setOnCheckedChangeListener { _, checked ->
            prefs.edit().putBoolean(KEY_CASE_SENSITIVE, checked).apply()
        }

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
        prefs.edit()
            .putString(KEY_KEYWORD, keywordInput.text.toString())
            .putBoolean(KEY_CASE_SENSITIVE, caseSensitiveCheck.isChecked)
            .putStringSet(KEY_SELECTED_TYPES, selectedFileTypes.mapTo(linkedSetOf()) { it.name })
            .apply()
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
            text = "后台搜索 TXT、PDF、文档和表格；每个文件首次命中后立即搜索下一个"
            textSize = 14f
            setTextColor(Color.rgb(95, 95, 95))
            setPadding(0, dp(4), 0, dp(14))
        })

        root.addView(Button(this).apply {
            text = "选择总文件夹"
            setOnClickListener { chooseFolder.launch(rootUri) }
        }, matchWrap())

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
            setOnClickListener { showFolderSelectionDialog() }
        }
        root.addView(chooseRangeButton, matchWrap())

        rangeText = TextView(this).apply {
            textSize = 14f
            setTextColor(Color.rgb(85, 85, 85))
            setPadding(0, dp(6), 0, dp(8))
        }
        root.addView(rangeText)

        chooseTypesButton = Button(this).apply {
            text = "选择搜索文件类型"
            setOnClickListener { showFileTypeDialog() }
        }
        root.addView(chooseTypesButton, matchWrap())

        typeText = TextView(this).apply {
            textSize = 14f
            setTextColor(Color.rgb(85, 85, 85))
            setPadding(0, dp(6), 0, dp(12))
        }
        root.addView(typeText)

        keywordInput = EditText(this).apply {
            hint = "输入需要搜索的文字"
            textSize = 17f
            isSingleLine = true
        }
        root.addView(keywordInput, matchWrap())

        caseSensitiveCheck = CheckBox(this).apply {
            text = "区分大小写"
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
        root.addView(
            listView,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        )

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
            val hasSavedSelection = prefs.contains(KEY_SELECTED_FOLDERS)
            val saved = prefs.getStringSet(KEY_SELECTED_FOLDERS, emptySet()).orEmpty()
            selectedFolderUris = when {
                forceSelectAll -> choices.mapTo(mutableSetOf()) { it.uri }
                sameRoot && hasSavedSelection -> choices.filter { it.uri in saved }.mapTo(mutableSetOf()) { it.uri }
                else -> choices.mapTo(mutableSetOf()) { it.uri }
            }
            saveFolderSelection()
            updateRangeSummary()

            if (showDialog) showFolderSelectionDialog()
        }
    }

    private fun showFolderSelectionDialog() {
        if (folderChoices.isEmpty()) {
            Toast.makeText(this, "该总文件夹下没有一级子文件夹，将只搜索根目录文件", Toast.LENGTH_LONG).show()
            return
        }
        val listView = ListView(this).apply {
            choiceMode = ListView.CHOICE_MODE_MULTIPLE
            adapter = ArrayAdapter(
                this@MainActivity,
                android.R.layout.simple_list_item_multiple_choice,
                folderChoices.map { it.name }
            )
            folderChoices.forEachIndexed { index, choice ->
                setItemChecked(index, choice.uri in selectedFolderUris)
            }
        }
        val view = selectionView(
            "默认全选。点选每个子文件夹前面的勾选框；取消后，该文件夹及其所有下级内容都不会搜索。根目录文件始终参与搜索。",
            listView
        )
        val dialog = AlertDialog.Builder(this)
            .setTitle("选择参与搜索的子文件夹")
            .setView(view)
            .setNeutralButton("全选", null)
            .setNegativeButton("取消", null)
            .setPositiveButton("确定") { _, _ ->
                selectedFolderUris = folderChoices.indices
                    .filter { listView.isItemChecked(it) }
                    .mapTo(mutableSetOf()) { folderChoices[it].uri }
                saveFolderSelection()
                updateRangeSummary()
            }
            .create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener {
                folderChoices.indices.forEach { listView.setItemChecked(it, true) }
            }
        }
        dialog.show()
    }

    private fun showFileTypeDialog() {
        val values = SearchFileType.entries
        val listView = ListView(this).apply {
            choiceMode = ListView.CHOICE_MODE_MULTIPLE
            adapter = ArrayAdapter(
                this@MainActivity,
                android.R.layout.simple_list_item_multiple_choice,
                values.map { type ->
                    when (type) {
                        SearchFileType.TXT -> "TXT（.txt、.md、.log）"
                        SearchFileType.PDF -> "PDF（.pdf）"
                        SearchFileType.DOCUMENT -> "文档（.doc、.docx、.odt、.rtf）"
                        SearchFileType.SPREADSHEET -> "表格（.xls、.xlsx、.ods、.csv、.tsv）"
                    }
                }
            )
            values.forEachIndexed { index, type -> setItemChecked(index, type in selectedFileTypes) }
        }
        val view = selectionView(
            "默认搜索全部类型。可以取消不需要的类别；文档和表格按大类选择，不需要逐个扩展名设置。",
            listView
        )
        val dialog = AlertDialog.Builder(this)
            .setTitle("选择搜索文件类型")
            .setView(view)
            .setNeutralButton("全选", null)
            .setNegativeButton("取消", null)
            .setPositiveButton("确定") { _, _ ->
                selectedFileTypes = values.indices
                    .filter { listView.isItemChecked(it) }
                    .mapTo(linkedSetOf()) { values[it] }
                prefs.edit()
                    .putStringSet(KEY_SELECTED_TYPES, selectedFileTypes.mapTo(linkedSetOf()) { it.name })
                    .apply()
                updateTypeSummary()
            }
            .create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener {
                values.indices.forEach { listView.setItemChecked(it, true) }
            }
        }
        dialog.show()
    }

    private fun selectionView(description: String, listView: ListView): View {
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(8), dp(4), dp(8), 0)
            addView(TextView(this@MainActivity).apply {
                text = description
                textSize = 14f
                setTextColor(Color.rgb(80, 80, 80))
                setPadding(dp(8), dp(4), dp(8), dp(8))
            })
            addView(
                listView,
                LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    (resources.displayMetrics.heightPixels * 0.46f).toInt()
                )
            )
        }
    }

    private fun saveFolderSelection() {
        prefs.edit()
            .putString(KEY_SELECTION_ROOT, rootUri?.toString())
            .putStringSet(KEY_SELECTED_FOLDERS, selectedFolderUris.toSet())
            .apply()
    }

    private fun updateRangeSummary() {
        rangeText.text = if (folderChoices.isEmpty()) {
            "搜索范围：总文件夹根目录"
        } else {
            val excluded = folderChoices.size - selectedFolderUris.size
            "搜索范围：根目录 + 已选 ${selectedFolderUris.size}/${folderChoices.size} 个一级子文件夹" +
                if (excluded > 0) "（已排除 $excluded 个）" else ""
        }
    }

    private fun updateTypeSummary() {
        typeText.text = "文件类型：${SearchFileType.labels(selectedFileTypes)}"
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
        if (selectedFileTypes.isEmpty()) {
            Toast.makeText(this, "请至少选择一种文件类型", Toast.LENGTH_SHORT).show()
            return
        }

        prefs.edit()
            .putString(KEY_KEYWORD, keyword)
            .putBoolean(KEY_CASE_SENSITIVE, caseSensitiveCheck.isChecked)
            .putStringSet(KEY_SELECTED_TYPES, selectedFileTypes.mapTo(linkedSetOf()) { it.name })
            .apply()

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
            .putStringArrayListExtra(
                SearchService.EXTRA_SELECTED_FILE_TYPES,
                ArrayList(selectedFileTypes.map { it.name })
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
            keywordInput.setSelection(keywordInput.text.length)
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
        private const val KEY_SELECTED_TYPES = "selectedFileTypes"
        private const val KEY_KEYWORD = "keyword"
        private const val KEY_CASE_SENSITIVE = "caseSensitive"
    }
}
