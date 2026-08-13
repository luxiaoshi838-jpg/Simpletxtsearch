from pathlib import Path
import runpy

# First apply the parser/resource cleanup baseline:
# - single-pass streamed text reading
# - bounded PDFBox memory + deterministic close
# - streamed legacy DOC/RTF where possible
# - deterministic XML reader close for DOCX/XLSX/ODT/ODS
runpy.run_path('desktop/tools/optimize_content_v124.py', run_name='__main__')

source_path = Path('desktop/src/main/java/com/luxiaoshi/simpletxtsearch/pc/SimpleTxtSearchPc.java')
pom_path = Path('desktop/pom.xml')
text = source_path.read_text(encoding='utf-8')
pom = pom_path.read_text(encoding='utf-8')


def replace_once(old: str, new: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f'Expected v1.2.4 fragment not found: {old[:180]!r}')
    text = text.replace(old, new, 1)


# UI + bounded parallel batch-search imports.
replace_once('import javax.swing.JCheckBox;\n', 'import javax.swing.JCheckBox;\nimport javax.swing.JComboBox;\n')
replace_once('import java.util.Set;\n', 'import java.util.Set;\nimport java.util.concurrent.CountDownLatch;\n')
replace_once(
    'import java.util.concurrent.CancellationException;\n',
    'import java.util.concurrent.CancellationException;\n'
    'import java.util.concurrent.ConcurrentLinkedQueue;\n'
    'import java.util.concurrent.ExecutorService;\n'
    'import java.util.concurrent.Executors;\n'
    'import java.util.concurrent.Semaphore;\n'
    'import java.util.concurrent.ThreadFactory;\n'
    'import java.util.concurrent.TimeUnit;\n'
    'import java.util.concurrent.atomic.AtomicInteger;\n'
    'import java.util.concurrent.atomic.AtomicLong;\n'
    'import java.util.concurrent.atomic.AtomicReference;\n'
)

replace_once(
    '    private static final int MAX_DISPLAY_RESULTS = 5000;\n',
    '    private static final int SEARCH_THREADS = Math.max(2, Math.min(4, Runtime.getRuntime().availableProcessors()));\n'
    '    private static final int HEAVY_PARSER_LIMIT = Math.min(2, SEARCH_THREADS);\n'
    '    private static final int DEFAULT_BATCH_SIZE = 200;\n'
    '    private static final Integer[] BATCH_SIZE_OPTIONS = {50, 100, 200, 500, 1000};\n'
)
replace_once('    private static final String PREF_TYPES = "types";\n', '    private static final String PREF_TYPES = "types";\n    private static final String PREF_BATCH_SIZE = "batchSize";\n')
replace_once(
    '    private final JCheckBox caseSensitiveBox = new JCheckBox("区分大小写");\n',
    '    private final JCheckBox caseSensitiveBox = new JCheckBox("区分大小写");\n'
    '    private final JComboBox<Integer> batchSizeBox = new JComboBox<>(BATCH_SIZE_OPTIONS);\n'
)
replace_once('        super("简搜 PC 1.2.4");\n', '        super("简搜 PC 1.2.7");\n')
replace_once(
    '        JLabel description = new JLabel("搜索文件正文：关键词用空格分隔，最多 10 个；同一文件正文必须同时包含全部关键词才会匹配。双击结果可打开文件。");\n',
    '        JLabel description = new JLabel("多线程搜索文件正文：按文件夹分批处理；每批结束即释放扫描资源。结果持续累计，双击结果直接打开原文件。");\n'
)

# Batch size is a per-batch memory/work limit, never a total-search limit.
replace_once(
    '''        JPanel typePanel = new JPanel(new FlowLayout(FlowLayout.LEFT, 10, 0));\n        typePanel.add(txtBox);\n        typePanel.add(pdfBox);\n        typePanel.add(documentBox);\n        typePanel.add(spreadsheetBox);\n''',
    '''        JPanel typePanel = new JPanel(new FlowLayout(FlowLayout.LEFT, 10, 0));\n        typePanel.add(txtBox);\n        typePanel.add(pdfBox);\n        typePanel.add(documentBox);\n        typePanel.add(spreadsheetBox);\n        typePanel.add(new JLabel("单批任务上限"));\n        batchSizeBox.setEditable(true);\n        batchSizeBox.setSelectedItem(DEFAULT_BATCH_SIZE);\n        batchSizeBox.setToolTipText("只限制当前批次文件数，不限制总搜索数量；结果跨批次持续累计");\n        typePanel.add(batchSizeBox);\n'''
)

replace_once(
    '        caseSensitiveBox.setSelected(preferences.getBoolean(PREF_CASE, false));\n',
    '        caseSensitiveBox.setSelected(preferences.getBoolean(PREF_CASE, false));\n'
    '        batchSizeBox.setSelectedItem(preferences.getInt(PREF_BATCH_SIZE, DEFAULT_BATCH_SIZE));\n'
)

replace_once(
    '''        savePreferences(categories);\n        resultModel.clear();\n        currentPathLabel.setText("当前：准备扫描……");\n        currentWorker = new SearchWorker(rootFolder, List.copyOf(selectedChildFolders), keywords, caseSensitiveBox.isSelected(), categories);\n        startButton.setEnabled(false);\n        stopButton.setEnabled(true);\n        statusLabel.setText("正在准备正文搜索……");\n        currentWorker.execute();\n''',
    '''        int batchSize;\n        try {\n            batchSize = parseBatchSize();\n        } catch (IllegalArgumentException error) {\n            JOptionPane.showMessageDialog(this, error.getMessage(), "单批任务上限不符合要求", JOptionPane.WARNING_MESSAGE);\n            return;\n        }\n\n        savePreferences(categories, batchSize);\n        resultModel.clear();\n        currentPathLabel.setText("当前：准备扫描……");\n        currentWorker = new SearchWorker(rootFolder, List.copyOf(selectedChildFolders), keywords, caseSensitiveBox.isSelected(), categories, batchSize);\n        startButton.setEnabled(false);\n        stopButton.setEnabled(true);\n        statusLabel.setText("正在准备正文搜索：" + SEARCH_THREADS + "线程，单批最多 " + batchSize + " 个文件……");\n        currentWorker.execute();\n'''
)

replace_once(
    '''    private void savePreferences(EnumSet<FileCategory> categories) {\n        preferences.put(PREF_KEYWORDS, keywordField.getText().trim());\n        preferences.putBoolean(PREF_CASE, caseSensitiveBox.isSelected());\n        preferences.put(PREF_TYPES, categories.stream().map(Enum::name).sorted().reduce((left, right) -> left + "," + right).orElse(""));\n    }\n''',
    '''    private int parseBatchSize() {\n        Object raw = batchSizeBox.getEditor().getItem();\n        try {\n            int value = Integer.parseInt(String.valueOf(raw).trim());\n            if (value < 10 || value > 5000) throw new NumberFormatException();\n            return value;\n        } catch (NumberFormatException error) {\n            throw new IllegalArgumentException("单批任务上限请输入 10–5000 之间的整数；它只限制当前批次，不限制总搜索数量。");\n        }\n    }\n\n    private void savePreferences(EnumSet<FileCategory> categories, int batchSize) {\n        preferences.put(PREF_KEYWORDS, keywordField.getText().trim());\n        preferences.putBoolean(PREF_CASE, caseSensitiveBox.isSelected());\n        preferences.put(PREF_TYPES, categories.stream().map(Enum::name).sorted().reduce((left, right) -> left + "," + right).orElse(""));\n        preferences.putInt(PREF_BATCH_SIZE, batchSize);\n    }\n'''
)

# Replace single-thread SearchWorker with folder-queue + per-folder batches.
start_marker = '    private final class SearchWorker extends SwingWorker<Void, ResultItem> {'
end_marker = '    private enum FileCategory {'
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit('SearchWorker markers not found after v1.2.4 patch')

worker = r'''    private final class SearchWorker extends SwingWorker<Void, ResultItem> {
        private final Path searchRoot;
        private final List<Path> selectedRoots;
        private final List<String> keywords;
        private final boolean caseSensitive;
        private final EnumSet<FileCategory> categories;
        private final int batchSize;

        private final AtomicInteger visited = new AtomicInteger();
        private final AtomicInteger scanned = new AtomicInteger();
        private final AtomicInteger matched = new AtomicInteger();
        private final AtomicInteger failed = new AtomicInteger();
        private final AtomicInteger skippedDirectories = new AtomicInteger();
        private final AtomicInteger completedBatches = new AtomicInteger();
        private final AtomicInteger activeThreads = new AtomicInteger();
        private final AtomicReference<Path> currentFolder = new AtomicReference<>();
        private final AtomicReference<Path> currentPath = new AtomicReference<>();
        private final AtomicLong lastStatusUpdateNanos = new AtomicLong();
        private final ConcurrentLinkedQueue<ResultItem> pendingResults = new ConcurrentLinkedQueue<>();
        private final Semaphore heavyParserSlots = new Semaphore(HEAVY_PARSER_LIMIT);
        private ExecutorService executor;

        private SearchWorker(Path searchRoot, List<Path> selectedRoots, List<String> keywords, boolean caseSensitive, EnumSet<FileCategory> categories, int batchSize) {
            this.searchRoot = searchRoot;
            this.selectedRoots = selectedRoots;
            this.keywords = keywords;
            this.caseSensitive = caseSensitive;
            this.categories = categories;
            this.batchSize = batchSize;
        }

        @Override
        protected Void doInBackground() throws Exception {
            AtomicInteger threadNumber = new AtomicInteger(1);
            ThreadFactory factory = runnable -> {
                Thread thread = new Thread(runnable, "SimpleSearch-content-" + threadNumber.getAndIncrement());
                thread.setDaemon(true);
                return thread;
            };
            executor = Executors.newFixedThreadPool(SEARCH_THREADS, factory);

            try {
                // Root folder: scan direct files only. Unselected first-level folders are never traversed.
                processFolder(searchRoot, false, null);

                // The task queue is folders. It has no total cap and only stores lightweight Path objects.
                Deque<Path> folderQueue = new ArrayDeque<>();
                for (Path selected : selectedRoots) {
                    if (isExcludedDirectory(selected)) skippedDirectories.incrementAndGet();
                    else folderQueue.addLast(selected);
                }

                while (!folderQueue.isEmpty()) {
                    checkCancelled();
                    Path folder = folderQueue.removeFirst();
                    processFolder(folder, true, folderQueue);
                }

                drainResults();
                updateStatus(true, 0);
                return null;
            } finally {
                if (executor != null) {
                    executor.shutdownNow();
                    try {
                        executor.awaitTermination(2, TimeUnit.SECONDS);
                    } catch (InterruptedException ignored) {
                        Thread.currentThread().interrupt();
                    }
                }
                drainResults();
            }
        }

        private void processFolder(Path folder, boolean collectChildren, Deque<Path> folderQueue) {
            checkCancelled();
            currentFolder.set(folder);
            List<Path> batch = new ArrayList<>(batchSize);

            try (var stream = Files.newDirectoryStream(folder)) {
                for (Path entry : stream) {
                    checkCancelled();
                    if (Files.isDirectory(entry)) {
                        if (collectChildren && folderQueue != null) {
                            if (isExcludedDirectory(entry)) skippedDirectories.incrementAndGet();
                            else folderQueue.addLast(entry);
                        }
                        continue;
                    }
                    if (!Files.isRegularFile(entry)) continue;
                    visited.incrementAndGet();
                    FileCategory category = FileCategory.from(entry);
                    if (category == null || !categories.contains(category)) continue;

                    batch.add(entry);
                    if (batch.size() >= batchSize) {
                        runBatch(batch);
                        batch.clear();
                        releaseAfterBatchIfNeeded();
                    }
                }
            } catch (IOException error) {
                failed.incrementAndGet();
            }

            if (!batch.isEmpty()) {
                runBatch(batch);
                batch.clear();
                releaseAfterBatchIfNeeded();
            }
        }

        private boolean isExcludedDirectory(Path dir) {
            Path name = dir.getFileName();
            if (name == null) return false;
            return EXCLUDED_DIRECTORY_NAMES.contains(name.toString().toLowerCase(Locale.ROOT));
        }

        private void runBatch(List<Path> files) {
            checkCancelled();
            int thisBatchSize = files.size();
            CountDownLatch latch = new CountDownLatch(thisBatchSize);

            for (Path file : files) {
                executor.execute(() -> {
                    activeThreads.incrementAndGet();
                    try {
                        scanContent(file);
                    } finally {
                        activeThreads.decrementAndGet();
                        latch.countDown();
                    }
                });
            }

            while (latch.getCount() > 0) {
                checkCancelled();
                try {
                    if (latch.await(100, TimeUnit.MILLISECONDS)) break;
                } catch (InterruptedException error) {
                    Thread.currentThread().interrupt();
                    throw new CancellationException();
                }
                drainResults();
                updateStatus(false, thisBatchSize);
            }

            completedBatches.incrementAndGet();
            drainResults();
            updateStatus(false, thisBatchSize);
        }

        private void scanContent(Path file) {
            if (isCancelled() || Thread.currentThread().isInterrupted()) return;
            currentPath.set(file);
            boolean heavy = isHeavyFormat(file);
            boolean acquired = false;
            try {
                if (heavy) {
                    heavyParserSlots.acquire();
                    acquired = true;
                }
                scanned.incrementAndGet();
                boolean hit = ContentSearch.contains(file, keywords, caseSensitive, this::isCancelled);
                if (hit) {
                    matched.incrementAndGet();
                    // Results are cumulative across every folder and batch.
                    // Only a lightweight Path is retained; file body/parser/cache never escapes ContentSearch.
                    pendingResults.add(new ResultItem(file));
                }
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            } catch (CancellationException ignored) {
                // Search cancellation.
            } catch (Exception error) {
                failed.incrementAndGet();
            } finally {
                if (acquired) heavyParserSlots.release();
            }
        }

        private boolean isHeavyFormat(Path file) {
            String name = file.getFileName().toString().toLowerCase(Locale.ROOT);
            return name.endsWith(".pdf") || name.endsWith(".doc") || name.endsWith(".xls");
        }

        private void drainResults() {
            List<ResultItem> chunk = new ArrayList<>(RESULT_BATCH_SIZE);
            ResultItem item;
            while ((item = pendingResults.poll()) != null) {
                chunk.add(item);
                if (chunk.size() >= RESULT_BATCH_SIZE) {
                    publish(chunk.toArray(ResultItem[]::new));
                    chunk.clear();
                }
            }
            if (!chunk.isEmpty()) publish(chunk.toArray(ResultItem[]::new));
        }

        private void releaseAfterBatchIfNeeded() {
            // Do not force GC per file or per normal batch: that slows scanning.
            // Every stream/parser is already closed at file completion. Only request GC if heap is truly pressured.
            Runtime runtime = Runtime.getRuntime();
            long used = runtime.totalMemory() - runtime.freeMemory();
            long max = runtime.maxMemory();
            if (max > 0 && used * 100L / max >= 75L) System.gc();
        }

        private void updateStatus(boolean force, int currentBatchSize) {
            long now = System.nanoTime();
            long previous = lastStatusUpdateNanos.get();
            if (!force && now - previous < STATUS_UPDATE_INTERVAL_NANOS) return;
            if (!force && !lastStatusUpdateNanos.compareAndSet(previous, now)) return;
            if (force) lastStatusUpdateNanos.set(now);

            int visitedSnapshot = visited.get();
            int scannedSnapshot = scanned.get();
            int matchedSnapshot = matched.get();
            int failedSnapshot = failed.get();
            int directorySnapshot = skippedDirectories.get();
            int batchSnapshot = completedBatches.get();
            int activeSnapshot = activeThreads.get();
            Path folderSnapshot = currentFolder.get();
            Path pathSnapshot = currentPath.get();

            SwingUtilities.invokeLater(() -> {
                if (currentWorker != this) return;
                statusLabel.setText("正文搜索 " + SEARCH_THREADS + "线程：遍历 " + visitedSnapshot
                    + " 个，读取正文 " + scannedSnapshot + " 个，累计结果 " + matchedSnapshot
                    + " 个；完成 " + batchSnapshot + " 批，当前批 " + currentBatchSize + "/" + batchSize
                    + "，活动线程 " + activeSnapshot
                    + (directorySnapshot > 0 ? "，排除目录 " + directorySnapshot + " 个" : "")
                    + (failedSnapshot > 0 ? "，读取失败 " + failedSnapshot + " 个" : ""));
                currentPathLabel.setText("文件夹：" + abbreviatePath(folderSnapshot) + "    最近文件：" + abbreviatePath(pathSnapshot));
                currentPathLabel.setToolTipText(pathSnapshot == null ? "" : pathSnapshot.toString());
            });
        }

        private String abbreviatePath(Path path) {
            if (path == null) return "—";
            String value = path.toString();
            int max = 100;
            return value.length() <= max ? value : "…" + value.substring(value.length() - max + 1);
        }

        private void checkCancelled() {
            if (isCancelled() || Thread.currentThread().isInterrupted()) throw new CancellationException();
        }

        @Override
        protected void process(List<ResultItem> chunks) {
            // Never clear previous matches here: result list accumulates until the search ends.
            for (ResultItem item : chunks) resultModel.addElement(item);
        }

        @Override
        protected void done() {
            if (executor != null) executor.shutdownNow();
            drainResults();
            startButton.setEnabled(true);
            stopButton.setEnabled(false);
            int visitedCount = visited.get();
            int scannedCount = scanned.get();
            int matchedCount = matched.get();
            int failedCount = failed.get();
            int directoryCount = skippedDirectories.get();
            if (isCancelled()) {
                statusLabel.setText("正文搜索已停止：遍历 " + visitedCount + " 个文件，读取正文 " + scannedCount
                    + " 个，累计结果 " + matchedCount + " 个；已完成 " + completedBatches.get() + " 批");
            } else {
                try {
                    get();
                    statusLabel.setText("正文搜索完成：" + SEARCH_THREADS + "线程，遍历 " + visitedCount + " 个文件，读取正文 "
                        + scannedCount + " 个，累计结果 " + matchedCount + " 个；完成 " + completedBatches.get() + " 批"
                        + (directoryCount > 0 ? "，排除目录 " + directoryCount + " 个" : "")
                        + (failedCount > 0 ? "，读取失败 " + failedCount + " 个" : ""));
                } catch (Exception error) {
                    statusLabel.setText("搜索失败：" + (error.getCause() == null ? error.getMessage() : error.getCause().getMessage()));
                }
            }
            pendingResults.clear();
            currentFolder.set(null);
            currentPath.set(null);
            executor = null;
            currentWorker = null;
        }
    }

'''
text = text[:start] + worker + text[end:]

source_path.write_text(text, encoding='utf-8')

# v1.2.4 baseline already changed Maven version/finalName; advance both consistently.
pom = pom.replace('<version>1.2.4</version>\n    <name>简搜 PC</name>', '<version>1.2.7</version>\n    <name>简搜 PC</name>', 1)
pom = pom.replace('<finalName>simpletxtsearch-pc-1.2.4</finalName>', '<finalName>simpletxtsearch-pc-1.2.7</finalName>', 1)
pom_path.write_text(pom, encoding='utf-8')

print('Applied v1.2.7 folder-queue + per-folder batch + cumulative-result parallel content search')
