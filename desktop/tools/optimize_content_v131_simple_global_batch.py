from pathlib import Path
import runpy

# Start from v1.2.9: multithreaded body search, cumulative clickable results,
# deterministic parser cleanup, and problem-folder auto skip.
runpy.run_path('desktop/tools/optimize_content_v129_problem_folder_skip.py', run_name='__main__')

source_path = Path('desktop/src/main/java/com/luxiaoshi/simpletxtsearch/pc/SimpleTxtSearchPc.java')
pom_path = Path('desktop/pom.xml')
text = source_path.read_text(encoding='utf-8')
pom = pom_path.read_text(encoding='utf-8')


def replace_once(old: str, new: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f'Expected v1.2.9 fragment not found: {old[:260]!r}')
    text = text.replace(old, new, 1)


# UI/version: one fixed global batch size. Remove the editable batch-size control.
replace_once('import javax.swing.JComboBox;\n', '')
replace_once(
    '    private static final int DEFAULT_BATCH_SIZE = 200;\n    private static final Integer[] BATCH_SIZE_OPTIONS = {50, 100, 200, 500, 1000};\n',
    '    private static final int FIXED_BATCH_SIZE = 200;\n'
)
replace_once('    private static final String PREF_BATCH_SIZE = "batchSize";\n', '')
replace_once('    private final JComboBox<Integer> batchSizeBox = new JComboBox<>(BATCH_SIZE_OPTIONS);\n', '')
replace_once('        super("简搜 PC 1.2.9");\n', '        super("简搜 PC 1.2.11");\n')
replace_once(
    '        JLabel description = new JLabel("多线程搜索文件正文：按文件夹分批处理；异常/无权限/链接类问题文件夹自动跳过，结果继续累计。");\n',
    '        JLabel description = new JLabel("多线程搜索文件正文：每批固定最多 200 个文件；批次结束释放扫描资源，结果持续累计。");\n'
)
replace_once(
    '''        typePanel.add(spreadsheetBox);\n        typePanel.add(new JLabel("单批任务上限"));\n        batchSizeBox.setEditable(true);\n        batchSizeBox.setSelectedItem(DEFAULT_BATCH_SIZE);\n        batchSizeBox.setToolTipText("只限制当前批次文件数，不限制总搜索数量；结果跨批次持续累计");\n        typePanel.add(batchSizeBox);\n''',
    '''        typePanel.add(spreadsheetBox);\n'''
)
replace_once('        batchSizeBox.setSelectedItem(preferences.getInt(PREF_BATCH_SIZE, DEFAULT_BATCH_SIZE));\n', '')

replace_once(
    '''        int batchSize;\n        try {\n            batchSize = parseBatchSize();\n        } catch (IllegalArgumentException error) {\n            JOptionPane.showMessageDialog(this, error.getMessage(), "单批任务上限不符合要求", JOptionPane.WARNING_MESSAGE);\n            return;\n        }\n\n        savePreferences(categories, batchSize);\n        resultModel.clear();\n        currentPathLabel.setText("当前：准备扫描……");\n        currentWorker = new SearchWorker(rootFolder, List.copyOf(selectedChildFolders), keywords, caseSensitiveBox.isSelected(), categories, batchSize);\n        startButton.setEnabled(false);\n        stopButton.setEnabled(true);\n        statusLabel.setText("正在准备正文搜索：" + SEARCH_THREADS + "线程，单批最多 " + batchSize + " 个文件……");\n        currentWorker.execute();\n''',
    '''        savePreferences(categories);\n        resultModel.clear();\n        currentPathLabel.setText("当前：准备扫描……");\n        currentWorker = new SearchWorker(rootFolder, List.copyOf(selectedChildFolders), keywords, caseSensitiveBox.isSelected(), categories);\n        startButton.setEnabled(false);\n        stopButton.setEnabled(true);\n        statusLabel.setText("已搜索 0 | 当前批 0/0 | 结果 0");\n        currentWorker.execute();\n'''
)

replace_once(
    '''    private int parseBatchSize() {\n        Object raw = batchSizeBox.getEditor().getItem();\n        try {\n            int value = Integer.parseInt(String.valueOf(raw).trim());\n            if (value < 10 || value > 5000) throw new NumberFormatException();\n            return value;\n        } catch (NumberFormatException error) {\n            throw new IllegalArgumentException("单批任务上限请输入 10–5000 之间的整数；它只限制当前批次，不限制总搜索数量。");\n        }\n    }\n\n    private void savePreferences(EnumSet<FileCategory> categories, int batchSize) {\n        preferences.put(PREF_KEYWORDS, keywordField.getText().trim());\n        preferences.putBoolean(PREF_CASE, caseSensitiveBox.isSelected());\n        preferences.put(PREF_TYPES, categories.stream().map(Enum::name).sorted().reduce((left, right) -> left + "," + right).orElse(""));\n        preferences.putInt(PREF_BATCH_SIZE, batchSize);\n    }\n''',
    '''    private void savePreferences(EnumSet<FileCategory> categories) {\n        preferences.put(PREF_KEYWORDS, keywordField.getText().trim());\n        preferences.putBoolean(PREF_CASE, caseSensitiveBox.isSelected());\n        preferences.put(PREF_TYPES, categories.stream().map(Enum::name).sorted().reduce((left, right) -> left + "," + right).orElse(""));\n    }\n'''
)

# Replace the v1.2.9 worker wholesale so the model is simple:
# enumerate eligible files across folders -> fill one global 200-file batch -> search -> release -> next batch.
start_marker = '    private final class SearchWorker extends SwingWorker<Void, ResultItem> {'
end_marker = '    private enum FileCategory {'
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit('SearchWorker markers not found after v1.2.9 patch')

worker = r'''    private final class SearchWorker extends SwingWorker<Void, ResultItem> {
        private final Path searchRoot;
        private final List<Path> selectedRoots;
        private final List<String> keywords;
        private final boolean caseSensitive;
        private final EnumSet<FileCategory> categories;

        private final AtomicInteger searched = new AtomicInteger();
        private final AtomicInteger matched = new AtomicInteger();
        private final AtomicInteger failed = new AtomicInteger();
        private final AtomicInteger skippedDirectories = new AtomicInteger();
        private final AtomicInteger skippedProblemFolders = new AtomicInteger();
        private final AtomicInteger currentBatchCompleted = new AtomicInteger();
        private final AtomicInteger currentBatchTotal = new AtomicInteger();
        private final AtomicInteger activeThreads = new AtomicInteger();
        private final AtomicReference<Path> currentPath = new AtomicReference<>();
        private final AtomicReference<Path> lastSkippedFolder = new AtomicReference<>();
        private final AtomicLong lastStatusUpdateNanos = new AtomicLong();
        private final ConcurrentLinkedQueue<ResultItem> pendingResults = new ConcurrentLinkedQueue<>();
        private final Semaphore heavyParserSlots = new Semaphore(HEAVY_PARSER_LIMIT);
        private ExecutorService executor;

        private SearchWorker(Path searchRoot, List<Path> selectedRoots, List<String> keywords, boolean caseSensitive, EnumSet<FileCategory> categories) {
            this.searchRoot = searchRoot;
            this.selectedRoots = selectedRoots;
            this.keywords = keywords;
            this.caseSensitive = caseSensitive;
            this.categories = categories;
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
            List<Path> batch = new ArrayList<>(FIXED_BATCH_SIZE);

            try {
                // Root direct files are eligible, but unselected first-level subfolders are not traversed.
                collectFolder(searchRoot, false, null, batch);

                Deque<Path> folderQueue = new ArrayDeque<>();
                for (Path selected : selectedRoots) {
                    if (isExcludedDirectory(selected)) {
                        skippedDirectories.incrementAndGet();
                    } else if (isProblemFolder(selected)) {
                        markProblemFolder(selected);
                    } else {
                        folderQueue.addLast(selected);
                    }
                }

                while (!folderQueue.isEmpty()) {
                    checkCancelled();
                    Path folder = folderQueue.removeFirst();
                    collectFolder(folder, true, folderQueue, batch);
                }

                // Only the final global batch may contain fewer than 200 files.
                if (!batch.isEmpty()) {
                    runBatch(batch);
                    batch.clear();
                    releaseAfterBatchIfNeeded();
                }

                drainResults();
                updateStatus(true);
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

        private void collectFolder(Path folder, boolean collectChildren, Deque<Path> folderQueue, List<Path> batch) {
            checkCancelled();
            if (isProblemFolder(folder)) {
                markProblemFolder(folder);
                return;
            }

            try (var stream = Files.newDirectoryStream(folder)) {
                var iterator = stream.iterator();
                while (true) {
                    checkCancelled();
                    Path entry;
                    try {
                        if (!iterator.hasNext()) break;
                        entry = iterator.next();
                    } catch (DirectoryIteratorException | SecurityException error) {
                        markProblemFolder(folder);
                        break;
                    }

                    try {
                        if (Files.isSymbolicLink(entry)) {
                            if (Files.isDirectory(entry)) markProblemFolder(entry);
                            continue;
                        }
                        if (Files.isDirectory(entry, LinkOption.NOFOLLOW_LINKS)) {
                            if (collectChildren && folderQueue != null) {
                                if (isExcludedDirectory(entry)) skippedDirectories.incrementAndGet();
                                else if (isProblemFolder(entry)) markProblemFolder(entry);
                                else folderQueue.addLast(entry);
                            }
                            continue;
                        }
                        if (!Files.isRegularFile(entry, LinkOption.NOFOLLOW_LINKS)) continue;
                    } catch (SecurityException error) {
                        continue;
                    }

                    FileCategory category = FileCategory.from(entry);
                    if (category == null || !categories.contains(category)) continue;

                    batch.add(entry);
                    if (batch.size() == FIXED_BATCH_SIZE) {
                        runBatch(batch);
                        batch.clear();
                        releaseAfterBatchIfNeeded();
                    }
                }
            } catch (IOException | SecurityException | DirectoryIteratorException error) {
                markProblemFolder(folder);
            }
        }

        private boolean isExcludedDirectory(Path dir) {
            Path name = dir == null ? null : dir.getFileName();
            if (name == null) return false;
            return EXCLUDED_DIRECTORY_NAMES.contains(name.toString().toLowerCase(Locale.ROOT));
        }

        private boolean isProblemFolder(Path dir) {
            try {
                if (dir == null) return true;
                if (Files.isSymbolicLink(dir)) return true;
                if (!Files.isDirectory(dir, LinkOption.NOFOLLOW_LINKS)) return true;
                return !Files.isReadable(dir);
            } catch (SecurityException error) {
                return true;
            }
        }

        private void markProblemFolder(Path dir) {
            skippedProblemFolders.incrementAndGet();
            lastSkippedFolder.set(dir);
        }

        private void runBatch(List<Path> files) {
            checkCancelled();
            int total = files.size();
            currentBatchTotal.set(total);
            currentBatchCompleted.set(0);
            updateStatus(true);

            CountDownLatch latch = new CountDownLatch(total);
            for (Path file : files) {
                executor.execute(() -> {
                    activeThreads.incrementAndGet();
                    try {
                        scanContent(file);
                    } finally {
                        activeThreads.decrementAndGet();
                        currentBatchCompleted.incrementAndGet();
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
                updateStatus(false);
            }

            drainResults();
            updateStatus(true); // show 200/200 (or e.g. 63/63) before the next batch resets to zero.
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
                boolean hit = ContentSearch.contains(file, keywords, caseSensitive, this::isCancelled);
                searched.incrementAndGet(); // only a normally completed body search counts as searched.
                if (hit) {
                    matched.incrementAndGet();
                    // Results always accumulate across all batches. Only the lightweight path is retained.
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
            // Parsers/streams close per file. Do not force GC normally; request it only under genuine heap pressure.
            Runtime runtime = Runtime.getRuntime();
            long used = runtime.totalMemory() - runtime.freeMemory();
            long max = runtime.maxMemory();
            if (max > 0 && used * 100L / max >= 75L) System.gc();
        }

        private void updateStatus(boolean force) {
            long now = System.nanoTime();
            long previous = lastStatusUpdateNanos.get();
            if (!force && now - previous < STATUS_UPDATE_INTERVAL_NANOS) return;
            if (!force && !lastStatusUpdateNanos.compareAndSet(previous, now)) return;
            if (force) lastStatusUpdateNanos.set(now);

            int searchedSnapshot = searched.get();
            int matchedSnapshot = matched.get();
            int batchDoneSnapshot = currentBatchCompleted.get();
            int batchTotalSnapshot = currentBatchTotal.get();
            Path pathSnapshot = currentPath.get();
            Path skippedSnapshot = lastSkippedFolder.get();

            SwingUtilities.invokeLater(() -> {
                if (currentWorker != this) return;
                statusLabel.setText("已搜索 " + searchedSnapshot + " | 当前批 " + batchDoneSnapshot + "/" + batchTotalSnapshot + " | 结果 " + matchedSnapshot);
                String detail = "最近文件：" + abbreviatePath(pathSnapshot);
                if (skippedSnapshot != null) detail += "    最近跳过：" + abbreviatePath(skippedSnapshot);
                currentPathLabel.setText(detail);
                currentPathLabel.setToolTipText(pathSnapshot == null ? "" : pathSnapshot.toString());
            });
        }

        private String abbreviatePath(Path path) {
            if (path == null) return "—";
            String value = path.toString();
            int max = 110;
            return value.length() <= max ? value : "…" + value.substring(value.length() - max + 1);
        }

        private void checkCancelled() {
            if (isCancelled() || Thread.currentThread().isInterrupted()) throw new CancellationException();
        }

        @Override
        protected void process(List<ResultItem> chunks) {
            // Never clear earlier matches here: results accumulate until the entire search ends.
            for (ResultItem item : chunks) resultModel.addElement(item);
        }

        @Override
        protected void done() {
            if (executor != null) executor.shutdownNow();
            drainResults();
            startButton.setEnabled(true);
            stopButton.setEnabled(false);

            int searchedCount = searched.get();
            int matchedCount = matched.get();
            int failedCount = failed.get();
            int excludedCount = skippedDirectories.get();
            int problemCount = skippedProblemFolders.get();

            if (isCancelled()) {
                statusLabel.setText("已停止 | 已搜索 " + searchedCount + " | 结果 " + matchedCount);
            } else {
                try {
                    get();
                    statusLabel.setText("完成 | 已搜索 " + searchedCount + " | 结果 " + matchedCount);
                } catch (Exception error) {
                    statusLabel.setText("搜索失败：" + (error.getCause() == null ? error.getMessage() : error.getCause().getMessage()));
                }
            }

            String summary = "搜索结束";
            if (problemCount > 0) summary += "，问题文件夹跳过 " + problemCount + " 个";
            if (excludedCount > 0) summary += "，排除目录 " + excludedCount + " 个";
            if (failedCount > 0) summary += "，文件读取失败 " + failedCount + " 个";
            currentPathLabel.setText(summary);

            pendingResults.clear();
            currentPath.set(null);
            lastSkippedFolder.set(null);
            executor = null;
            currentWorker = null;
        }
    }

'''
text = text[:start] + worker + text[end:]

pom = pom.replace('<version>1.2.9</version>\n    <name>简搜 PC</name>', '<version>1.2.11</version>\n    <name>简搜 PC</name>', 1)
pom = pom.replace('<finalName>simpletxtsearch-pc-1.2.9</finalName>', '<finalName>simpletxtsearch-pc-1.2.11</finalName>', 1)

source_path.write_text(text, encoding='utf-8')
pom_path.write_text(pom, encoding='utf-8')
print('Applied v1.2.11 simple global fixed-200 content-search batching')
