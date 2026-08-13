from pathlib import Path

source_path = Path('desktop/src/main/java/com/luxiaoshi/simpletxtsearch/pc/SimpleTxtSearchPc.java')
text = source_path.read_text(encoding='utf-8')


def replace_once(old: str, new: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f'Expected source fragment not found: {old[:120]!r}')
    text = text.replace(old, new, 1)


replace_once(
    '    private static final int MAX_KEYWORDS = 10;\n',
    '''    private static final int MAX_KEYWORDS = 10;\n'''
    '''    private static final long MAX_FILE_SIZE_BYTES = 50L * 1024L * 1024L;\n'''
    '''    private static final int MAX_DISPLAY_RESULTS = 5000;\n'''
    '''    private static final int RESULT_BATCH_SIZE = 50;\n'''
    '''    private static final long STATUS_UPDATE_INTERVAL_NANOS = 200_000_000L;\n'''
    '''    private static final Set<String> EXCLUDED_DIRECTORY_NAMES = Set.of(\n'''
    '''        ".git", "node_modules", ".venv", "venv", "__pycache__", "build", "dist"\n'''
    '''    );\n'''
)

replace_once('        super("简搜 PC 1.2.0");\n', '        super("简搜 PC 1.2.1");\n')
replace_once(
    '        JLabel description = new JLabel("每个关键词用空格分隔，最多 10 个；文件中必须同时包含全部关键词才会匹配。双击结果可打开文件。");\n',
    '        JLabel description = new JLabel("每个关键词用空格分隔，最多 10 个；完整扫描所选范围。大目录采用分批读取与分批显示，降低持续内存占用。");\n'
)

start_marker = '    private final class SearchWorker extends SwingWorker<Void, ResultItem> {'
end_marker = '    private enum FileCategory {'
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit('SearchWorker markers not found')

replacement = r'''    private final class SearchWorker extends SwingWorker<Void, ResultItem> {
        private final Path searchRoot;
        private final List<Path> selectedRoots;
        private final List<String> keywords;
        private final boolean caseSensitive;
        private final EnumSet<FileCategory> categories;
        private final List<ResultItem> resultBatch = new ArrayList<>(RESULT_BATCH_SIZE);
        private int scanned;
        private int matched;
        private int failed;
        private int skippedLarge;
        private int skippedDirectories;
        private int queuedForDisplay;
        private long lastStatusUpdateNanos;

        private SearchWorker(Path searchRoot, List<Path> selectedRoots, List<String> keywords, boolean caseSensitive, EnumSet<FileCategory> categories) {
            this.searchRoot = searchRoot;
            this.selectedRoots = selectedRoots;
            this.keywords = keywords;
            this.caseSensitive = caseSensitive;
            this.categories = categories;
        }

        @Override
        protected Void doInBackground() throws Exception {
            try {
                try (var stream = Files.newDirectoryStream(searchRoot)) {
                    for (Path entry : stream) {
                        checkCancelled();
                        if (Files.isRegularFile(entry)) scanFile(entry, safeFileSize(entry));
                    }
                }

                for (Path selected : selectedRoots) {
                    checkCancelled();
                    Files.walkFileTree(selected, new SimpleFileVisitor<>() {
                        @Override
                        public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
                            checkCancelled();
                            if (isExcludedDirectory(dir)) {
                                skippedDirectories++;
                                updateStatus(false);
                                return FileVisitResult.SKIP_SUBTREE;
                            }
                            return FileVisitResult.CONTINUE;
                        }

                        @Override
                        public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                            checkCancelled();
                            if (attrs.isRegularFile()) scanFile(file, attrs.size());
                            return FileVisitResult.CONTINUE;
                        }

                        @Override
                        public FileVisitResult visitFileFailed(Path file, IOException exc) {
                            failed++;
                            updateStatus(false);
                            return FileVisitResult.CONTINUE;
                        }
                    });
                }
                flushResultBatch();
                updateStatus(true);
                return null;
            } finally {
                flushResultBatch();
            }
        }

        private boolean isExcludedDirectory(Path dir) {
            Path name = dir.getFileName();
            if (name == null) return false;
            return EXCLUDED_DIRECTORY_NAMES.contains(name.toString().toLowerCase(Locale.ROOT));
        }

        private long safeFileSize(Path file) {
            try {
                return Files.size(file);
            } catch (IOException ignored) {
                return -1L;
            }
        }

        private void scanFile(Path file, long fileSize) {
            checkCancelled();
            FileCategory category = FileCategory.from(file);
            if (category == null || !categories.contains(category)) return;

            if (fileSize > MAX_FILE_SIZE_BYTES) {
                skippedLarge++;
                updateStatus(false);
                return;
            }

            boolean hit = false;
            try {
                hit = ContentSearch.contains(file, keywords, caseSensitive, this::isCancelled);
            } catch (CancellationException error) {
                throw error;
            } catch (Exception error) {
                failed++;
            }

            scanned++;
            if (hit) {
                matched++;
                if (queuedForDisplay < MAX_DISPLAY_RESULTS) {
                    resultBatch.add(new ResultItem(file));
                    queuedForDisplay++;
                    if (resultBatch.size() >= RESULT_BATCH_SIZE) flushResultBatch();
                }
            }
            updateStatus(false);
        }

        private void flushResultBatch() {
            if (resultBatch.isEmpty()) return;
            ResultItem[] batch = resultBatch.toArray(ResultItem[]::new);
            resultBatch.clear();
            publish(batch);
        }

        private void updateStatus(boolean force) {
            long now = System.nanoTime();
            if (!force && now - lastStatusUpdateNanos < STATUS_UPDATE_INTERVAL_NANOS) return;
            lastStatusUpdateNanos = now;

            int scannedSnapshot = scanned;
            int matchedSnapshot = matched;
            int failedSnapshot = failed;
            int largeSnapshot = skippedLarge;
            int directorySnapshot = skippedDirectories;
            int visibleSnapshot = Math.min(matchedSnapshot, MAX_DISPLAY_RESULTS);
            SwingUtilities.invokeLater(() -> {
                if (currentWorker != this) return;
                StringBuilder status = new StringBuilder("正在搜索：已扫描 ")
                    .append(scannedSnapshot)
                    .append(" 个文件，找到 ")
                    .append(matchedSnapshot)
                    .append(" 个");
                if (matchedSnapshot > MAX_DISPLAY_RESULTS) {
                    status.append("（界面显示前 ").append(visibleSnapshot).append(" 个，后台仍继续完整扫描）");
                }
                if (largeSnapshot > 0) status.append("，超 50 MB 跳过 ").append(largeSnapshot).append(" 个");
                if (directorySnapshot > 0) status.append("，排除目录 ").append(directorySnapshot).append(" 个");
                if (failedSnapshot > 0) status.append("，无法读取 ").append(failedSnapshot).append(" 个");
                statusLabel.setText(status.toString());
            });
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
            startButton.setEnabled(true);
            stopButton.setEnabled(false);
            String displaySuffix = matched > MAX_DISPLAY_RESULTS
                ? "；界面仅保留前 " + MAX_DISPLAY_RESULTS + " 个结果"
                : "";
            String skipSuffix = (skippedLarge > 0 ? "，超 50 MB 跳过 " + skippedLarge + " 个" : "")
                + (skippedDirectories > 0 ? "，排除目录 " + skippedDirectories + " 个" : "")
                + (failed > 0 ? "，无法读取 " + failed + " 个" : "");
            if (isCancelled()) {
                statusLabel.setText("搜索已停止：已扫描 " + scanned + " 个文件，找到 " + matched + " 个" + skipSuffix + displaySuffix);
            } else {
                try {
                    get();
                    statusLabel.setText("搜索完成：已扫描 " + scanned + " 个文件，找到 " + matched + " 个" + skipSuffix + displaySuffix);
                } catch (Exception error) {
                    statusLabel.setText("搜索失败：" + (error.getCause() == null ? error.getMessage() : error.getCause().getMessage()));
                }
            }
            resultBatch.clear();
            currentWorker = null;
        }
    }

'''

text = text[:start] + replacement + text[end:]
source_path.write_text(text, encoding='utf-8')
print(f'Patched {source_path}')
