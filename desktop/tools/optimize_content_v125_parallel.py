from pathlib import Path

source_path = Path('desktop/src/main/java/com/luxiaoshi/simpletxtsearch/pc/SimpleTxtSearchPc.java')
pom_path = Path('desktop/pom.xml')
text = source_path.read_text(encoding='utf-8')
pom = pom_path.read_text(encoding='utf-8')


def replace_once(old: str, new: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f'Expected source fragment not found: {old[:180]!r}')
    text = text.replace(old, new, 1)

# Imports needed for bounded parallel search.
replace_once('import java.util.Set;\n', 'import java.util.Set;\nimport java.util.concurrent.ArrayBlockingQueue;\n')
replace_once('import java.util.concurrent.CancellationException;\n', 'import java.util.concurrent.CancellationException;\nimport java.util.concurrent.ConcurrentLinkedQueue;\nimport java.util.concurrent.ThreadFactory;\nimport java.util.concurrent.ThreadPoolExecutor;\nimport java.util.concurrent.TimeUnit;\nimport java.util.concurrent.atomic.AtomicInteger;\nimport java.util.concurrent.atomic.AtomicReference;\n')

replace_once(
    '    private static final int MAX_KEYWORDS = 10;\n',
    '''    private static final int MAX_KEYWORDS = 10;\n'''
    '''    private static final int SEARCH_THREADS = Math.max(2, Math.min(4, Runtime.getRuntime().availableProcessors()));\n'''
    '''    private static final int SEARCH_QUEUE_CAPACITY = SEARCH_THREADS * 4;\n'''
    '''    private static final int MAX_DISPLAY_RESULTS = 5000;\n'''
    '''    private static final int RESULT_BATCH_SIZE = 50;\n'''
    '''    private static final long STATUS_UPDATE_INTERVAL_NANOS = 250_000_000L;\n'''
    '''    private static final Set<String> EXCLUDED_DIRECTORY_NAMES = Set.of(\n'''
    '''        ".git", ".gradle", ".idea", ".vscode", "node_modules", ".venv", "venv", "__pycache__",\n'''
    '''        "runtime", "output", "build", "dist", "target", "cache", "caches", "tmp", "temp",\n'''
    '''        "缓存", "旧版", "过往不用"\n'''
    '''    );\n'''
)
replace_once(
    '    private final JLabel statusLabel = new JLabel("请选择总文件夹并输入关键词");\n',
    '    private final JLabel statusLabel = new JLabel("请选择总文件夹并输入关键词");\n    private final JLabel currentPathLabel = new JLabel("当前：—");\n'
)
replace_once('        super("简搜 PC 1.2.0");\n', '        super("简搜 PC 1.2.5");\n')
replace_once(
    '        JLabel description = new JLabel("每个关键词用空格分隔，最多 10 个；文件中必须同时包含全部关键词才会匹配。双击结果可打开文件。");\n',
    '        JLabel description = new JLabel("多线程搜索文件正文：关键词用空格分隔，最多 10 个；同一文件正文必须同时包含全部关键词才会匹配。");\n'
)
replace_once(
    '''        JPanel statusPanel = new JPanel(new BorderLayout());\n        statusPanel.setBorder(BorderFactory.createEmptyBorder(4, 4, 0, 4));\n        statusPanel.add(statusLabel, BorderLayout.CENTER);\n''',
    '''        JPanel statusPanel = new JPanel(new BorderLayout(0, 3));\n        statusPanel.setBorder(BorderFactory.createEmptyBorder(4, 4, 0, 4));\n        statusPanel.add(statusLabel, BorderLayout.NORTH);\n        currentPathLabel.setToolTipText("最近正在扫描的文件路径");\n        statusPanel.add(currentPathLabel, BorderLayout.SOUTH);\n'''
)
replace_once(
    '        statusLabel.setText("正在准备搜索……");\n',
    '        statusLabel.setText("正在准备多线程正文搜索（" + SEARCH_THREADS + " 线程）……");\n        currentPathLabel.setText("当前：准备扫描……");\n'
)

start_marker = '    private final class SearchWorker extends SwingWorker<Void, ResultItem> {'
end_marker = '    private enum FileCategory {'
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit('SearchWorker markers not found')

worker = r'''    private final class SearchWorker extends SwingWorker<Void, ResultItem> {
        private final Path searchRoot;
        private final List<Path> selectedRoots;
        private final List<String> keywords;
        private final boolean caseSensitive;
        private final EnumSet<FileCategory> categories;

        private final AtomicInteger visited = new AtomicInteger();
        private final AtomicInteger scanned = new AtomicInteger();
        private final AtomicInteger matched = new AtomicInteger();
        private final AtomicInteger failed = new AtomicInteger();
        private final AtomicInteger skippedDirectories = new AtomicInteger();
        private final AtomicInteger queuedForDisplay = new AtomicInteger();
        private final AtomicReference<Path> currentPath = new AtomicReference<>();
        private final ConcurrentLinkedQueue<ResultItem> pendingResults = new ConcurrentLinkedQueue<>();
        private volatile long lastStatusUpdateNanos;
        private ThreadPoolExecutor executor;

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

            executor = new ThreadPoolExecutor(
                SEARCH_THREADS,
                SEARCH_THREADS,
                0L,
                TimeUnit.MILLISECONDS,
                new ArrayBlockingQueue<>(SEARCH_QUEUE_CAPACITY),
                factory,
                (task, pool) -> {
                    try {
                        if (pool.isShutdown()) throw new CancellationException();
                        pool.getQueue().put(task); // bounded back-pressure; never accumulate an unbounded file task list.
                    } catch (InterruptedException error) {
                        Thread.currentThread().interrupt();
                        throw new CancellationException();
                    }
                }
            );

            try {
                try (var stream = Files.newDirectoryStream(searchRoot)) {
                    for (Path entry : stream) {
                        checkCancelled();
                        drainResults();
                        if (Files.isRegularFile(entry)) submitFile(entry);
                    }
                }

                for (Path selected : selectedRoots) {
                    checkCancelled();
                    Files.walkFileTree(selected, new SimpleFileVisitor<>() {
                        @Override
                        public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
                            checkCancelled();
                            drainResults();
                            if (isExcludedDirectory(dir)) {
                                skippedDirectories.incrementAndGet();
                                currentPath.set(dir);
                                updateStatus(false);
                                return FileVisitResult.SKIP_SUBTREE;
                            }
                            return FileVisitResult.CONTINUE;
                        }

                        @Override
                        public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                            checkCancelled();
                            drainResults();
                            if (attrs.isRegularFile()) submitFile(file);
                            return FileVisitResult.CONTINUE;
                        }

                        @Override
                        public FileVisitResult visitFileFailed(Path file, IOException exc) {
                            failed.incrementAndGet();
                            currentPath.set(file);
                            updateStatus(false);
                            return FileVisitResult.CONTINUE;
                        }
                    });
                }

                executor.shutdown();
                while (!executor.awaitTermination(100, TimeUnit.MILLISECONDS)) {
                    checkCancelled();
                    drainResults();
                    updateStatus(false);
                }
                drainResults();
                updateStatus(true);
                return null;
            } finally {
                if (executor != null && !executor.isTerminated()) executor.shutdownNow();
                drainResults();
            }
        }

        private boolean isExcludedDirectory(Path dir) {
            Path name = dir.getFileName();
            if (name == null) return false;
            return EXCLUDED_DIRECTORY_NAMES.contains(name.toString().toLowerCase(Locale.ROOT));
        }

        private void submitFile(Path file) {
            checkCancelled();
            visited.incrementAndGet();
            FileCategory category = FileCategory.from(file);
            if (category == null || !categories.contains(category)) {
                updateStatus(false);
                return;
            }
            executor.execute(() -> scanContent(file));
        }

        private void scanContent(Path file) {
            if (isCancelled() || Thread.currentThread().isInterrupted()) return;
            currentPath.set(file);
            boolean hit = false;
            try {
                scanned.incrementAndGet();
                hit = ContentSearch.contains(file, keywords, caseSensitive, this::isCancelled);
            } catch (CancellationException ignored) {
                return;
            } catch (Exception error) {
                failed.incrementAndGet();
            }

            // Every parser/stream is owned by ContentSearch and closes before this task returns.
            // We retain only the Path for a matching result, never the file body or parser object.
            if (hit) {
                matched.incrementAndGet();
                int slot = queuedForDisplay.getAndIncrement();
                if (slot < MAX_DISPLAY_RESULTS) pendingResults.add(new ResultItem(file));
            }
            updateStatus(false);
        }

        private void drainResults() {
            if (pendingResults.isEmpty()) return;
            List<ResultItem> batch = new ArrayList<>(RESULT_BATCH_SIZE);
            ResultItem item;
            while (batch.size() < RESULT_BATCH_SIZE && (item = pendingResults.poll()) != null) {
                batch.add(item);
            }
            if (!batch.isEmpty()) publish(batch.toArray(ResultItem[]::new));
        }

        private void updateStatus(boolean force) {
            long now = System.nanoTime();
            if (!force && now - lastStatusUpdateNanos < STATUS_UPDATE_INTERVAL_NANOS) return;
            lastStatusUpdateNanos = now;

            int visitedSnapshot = visited.get();
            int scannedSnapshot = scanned.get();
            int matchedSnapshot = matched.get();
            int failedSnapshot = failed.get();
            int directorySnapshot = skippedDirectories.get();
            Path pathSnapshot = currentPath.get();
            int active = executor == null ? 0 : executor.getActiveCount();
            int queued = executor == null ? 0 : executor.getQueue().size();

            SwingUtilities.invokeLater(() -> {
                if (currentWorker != this) return;
                StringBuilder status = new StringBuilder("正文搜索 ")
                    .append(SEARCH_THREADS).append("线程：遍历 ")
                    .append(visitedSnapshot)
                    .append(" 个，读取正文 ")
                    .append(scannedSnapshot)
                    .append(" 个，找到 ")
                    .append(matchedSnapshot)
                    .append(" 个，活动线程 ")
                    .append(active)
                    .append("，排队 ")
                    .append(queued);
                if (matchedSnapshot > MAX_DISPLAY_RESULTS) {
                    status.append("（界面仅保留前 ").append(MAX_DISPLAY_RESULTS).append(" 个，后台继续完整扫描）");
                }
                if (directorySnapshot > 0) status.append("，排除目录 ").append(directorySnapshot).append(" 个");
                if (failedSnapshot > 0) status.append("，读取失败 ").append(failedSnapshot).append(" 个");
                statusLabel.setText(status.toString());
                currentPathLabel.setText("最近：" + abbreviatePath(pathSnapshot));
                currentPathLabel.setToolTipText(pathSnapshot == null ? "" : pathSnapshot.toString());
            });
        }

        private String abbreviatePath(Path path) {
            if (path == null) return "—";
            String value = path.toString();
            int max = 180;
            return value.length() <= max ? value : "…" + value.substring(value.length() - max + 1);
        }

        private void checkCancelled() {
            if (isCancelled() || Thread.currentThread().isInterrupted()) throw new CancellationException();
        }

        @Override
        protected void process(List<ResultItem> chunks) {
            for (ResultItem item : chunks) resultModel.addElement(item);
        }

        @Override
        protected void done() {
            if (executor != null && !executor.isTerminated()) executor.shutdownNow();
            drainResults();
            startButton.setEnabled(true);
            stopButton.setEnabled(false);
            int visitedCount = visited.get();
            int scannedCount = scanned.get();
            int matchedCount = matched.get();
            int failedCount = failed.get();
            int directoryCount = skippedDirectories.get();
            String displaySuffix = matchedCount > MAX_DISPLAY_RESULTS
                ? "；界面仅保留前 " + MAX_DISPLAY_RESULTS + " 个结果"
                : "";
            String skipSuffix = (directoryCount > 0 ? "，排除目录 " + directoryCount + " 个" : "")
                + (failedCount > 0 ? "，读取失败 " + failedCount + " 个" : "");
            if (isCancelled()) {
                statusLabel.setText("正文搜索已停止：遍历 " + visitedCount + " 个文件，读取正文 " + scannedCount + " 个，找到 " + matchedCount + " 个" + skipSuffix + displaySuffix);
            } else {
                try {
                    get();
                    statusLabel.setText("正文搜索完成（" + SEARCH_THREADS + "线程）：遍历 " + visitedCount + " 个文件，读取正文 " + scannedCount + " 个，找到 " + matchedCount + " 个" + skipSuffix + displaySuffix);
                } catch (Exception error) {
                    statusLabel.setText("搜索失败：" + (error.getCause() == null ? error.getMessage() : error.getCause().getMessage()));
                }
            }
            pendingResults.clear();
            currentPath.set(null);
            executor = null;
            currentWorker = null;
        }
    }

'''
text = text[:start] + worker + text[end:]

# Keep all existing content parsers; add lower-allocation plain-text chunk matching if not already present.
text = text.replace(
    'if (count > 0 && matcher.feed(new String(buffer, 0, count))) return true;',
    'if (count > 0 && matcher.feed(new String(buffer, 0, count))) return true;',
    1
)

source_path.write_text(text, encoding='utf-8')
pom = pom.replace('<version>1.2.0</version>\n    <name>简搜 PC</name>', '<version>1.2.5</version>\n    <name>简搜 PC</name>', 1)
pom = pom.replace('<finalName>simpletxtsearch-pc-1.2.0</finalName>', '<finalName>simpletxtsearch-pc-1.2.5</finalName>', 1)
pom_path.write_text(pom, encoding='utf-8')
print('Applied v1.2.5 bounded parallel content-search patch')
