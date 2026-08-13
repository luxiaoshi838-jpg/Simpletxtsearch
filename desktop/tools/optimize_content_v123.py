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


# Keep content search as the only search meaning. Optimize traversal/UI/result retention only.
replace_once(
    '    private static final int MAX_KEYWORDS = 10;\n',
    '''    private static final int MAX_KEYWORDS = 10;\n'''
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
replace_once('        super("简搜 PC 1.2.0");\n', '        super("简搜 PC 1.2.3");\n')
replace_once(
    '        JLabel description = new JLabel("每个关键词用空格分隔，最多 10 个；文件中必须同时包含全部关键词才会匹配。双击结果可打开文件。");\n',
    '        JLabel description = new JLabel("搜索文件正文：关键词用空格分隔，最多 10 个；同一文件正文必须同时包含全部关键词才会匹配。双击结果可打开文件。");\n'
)
replace_once(
    '''        JPanel statusPanel = new JPanel(new BorderLayout());\n        statusPanel.setBorder(BorderFactory.createEmptyBorder(4, 4, 0, 4));\n        statusPanel.add(statusLabel, BorderLayout.CENTER);\n''',
    '''        JPanel statusPanel = new JPanel(new BorderLayout(0, 3));\n        statusPanel.setBorder(BorderFactory.createEmptyBorder(4, 4, 0, 4));\n        statusPanel.add(statusLabel, BorderLayout.NORTH);\n        currentPathLabel.setToolTipText("当前正在扫描的文件路径");\n        statusPanel.add(currentPathLabel, BorderLayout.SOUTH);\n'''
)
replace_once(
    '        statusLabel.setText("正在准备搜索……");\n',
    '        statusLabel.setText("正在准备正文搜索……");\n        currentPathLabel.setText("当前：准备扫描……");\n'
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
        private final List<ResultItem> resultBatch = new ArrayList<>(RESULT_BATCH_SIZE);
        private int visited;
        private int scanned;
        private int matched;
        private int failed;
        private int skippedDirectories;
        private int queuedForDisplay;
        private long lastStatusUpdateNanos;
        private Path currentPath;

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
                // Root-level files are streamed directly; do not materialize/sort the entire list.
                try (var stream = Files.newDirectoryStream(searchRoot)) {
                    for (Path entry : stream) {
                        checkCancelled();
                        if (Files.isRegularFile(entry)) inspectFile(entry);
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
                                currentPath = dir;
                                updateStatus(false);
                                return FileVisitResult.SKIP_SUBTREE;
                            }
                            return FileVisitResult.CONTINUE;
                        }

                        @Override
                        public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                            checkCancelled();
                            if (attrs.isRegularFile()) inspectFile(file);
                            return FileVisitResult.CONTINUE;
                        }

                        @Override
                        public FileVisitResult visitFileFailed(Path file, IOException exc) {
                            failed++;
                            currentPath = file;
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

        private void inspectFile(Path file) {
            checkCancelled();
            visited++;
            currentPath = file;

            FileCategory category = FileCategory.from(file);
            if (category == null || !categories.contains(category)) {
                updateStatus(false);
                return;
            }

            boolean hit = false;
            try {
                scanned++;
                hit = ContentSearch.contains(file, keywords, caseSensitive, this::isCancelled);
            } catch (CancellationException error) {
                throw error;
            } catch (Exception error) {
                failed++;
            }

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

            int visitedSnapshot = visited;
            int scannedSnapshot = scanned;
            int matchedSnapshot = matched;
            int failedSnapshot = failed;
            int directorySnapshot = skippedDirectories;
            Path pathSnapshot = currentPath;

            SwingUtilities.invokeLater(() -> {
                if (currentWorker != this) return;
                StringBuilder status = new StringBuilder("正文搜索：遍历 ")
                    .append(visitedSnapshot)
                    .append(" 个文件，读取正文 ")
                    .append(scannedSnapshot)
                    .append(" 个，找到 ")
                    .append(matchedSnapshot)
                    .append(" 个");
                if (matchedSnapshot > MAX_DISPLAY_RESULTS) {
                    status.append("（界面仅保留前 ").append(MAX_DISPLAY_RESULTS).append(" 个，后台继续完整扫描）");
                }
                if (directorySnapshot > 0) status.append("，排除目录 ").append(directorySnapshot).append(" 个");
                if (failedSnapshot > 0) status.append("，读取失败 ").append(failedSnapshot).append(" 个");
                statusLabel.setText(status.toString());
                currentPathLabel.setText("当前：" + abbreviatePath(pathSnapshot));
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
            startButton.setEnabled(true);
            stopButton.setEnabled(false);
            String displaySuffix = matched > MAX_DISPLAY_RESULTS
                ? "；界面仅保留前 " + MAX_DISPLAY_RESULTS + " 个结果"
                : "";
            String skipSuffix = (skippedDirectories > 0 ? "，排除目录 " + skippedDirectories + " 个" : "")
                + (failed > 0 ? "，读取失败 " + failed + " 个" : "");
            if (isCancelled()) {
                statusLabel.setText("正文搜索已停止：遍历 " + visited + " 个文件，读取正文 " + scanned + " 个，找到 " + matched + " 个" + skipSuffix + displaySuffix);
            } else {
                try {
                    get();
                    statusLabel.setText("正文搜索完成：遍历 " + visited + " 个文件，读取正文 " + scanned + " 个，找到 " + matched + " 个" + skipSuffix + displaySuffix);
                } catch (Exception error) {
                    statusLabel.setText("搜索失败：" + (error.getCause() == null ? error.getMessage() : error.getCause().getMessage()));
                }
            }
            resultBatch.clear();
            currentWorker = null;
        }
    }

'''
text = text[:start] + worker + text[end:]

# Avoid retaining an entire RTF raw string and extracted string simultaneously.
old_rtf_start = text.find('        private static boolean containsRtf(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {')
old_rtf_end = text.find('        private static Charset detectCharset(Path file) throws IOException {', old_rtf_start)
if old_rtf_start < 0 or old_rtf_end < 0:
    raise SystemExit('RTF section markers not found')
rtf = r'''        private static boolean containsRtf(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {
            // RTF is parsed incrementally so the complete file and complete extracted text are never retained together.
            MultiMatcher matcher = new MultiMatcher(keywords, caseSensitive);
            try (Reader reader = Files.newBufferedReader(file, Charset.forName("windows-1252"))) {
                RtfStreamingParser parser = new RtfStreamingParser(matcher, cancelled);
                char[] buffer = new char[BUFFER_SIZE];
                int count;
                while ((count = reader.read(buffer)) >= 0) {
                    checkCancelled(cancelled);
                    if (count > 0 && parser.feed(buffer, count)) return true;
                }
                return parser.finish();
            }
        }

        private static final class RtfStreamingParser {
            private final MultiMatcher matcher;
            private final BooleanSupplier cancelled;
            private final StringBuilder plain = new StringBuilder(BUFFER_SIZE * 2);
            private int depth;
            private boolean escaped;

            private RtfStreamingParser(MultiMatcher matcher, BooleanSupplier cancelled) {
                this.matcher = matcher;
                this.cancelled = cancelled;
            }

            private boolean feed(char[] chars, int count) {
                for (int i = 0; i < count; i++) {
                    if ((i & 4095) == 0) checkCancelled(cancelled);
                    char ch = chars[i];
                    if (escaped) {
                        escaped = false;
                        // Control words are not needed for keyword matching; keep literal escaped braces/slashes.
                        if (ch == '\\' || ch == '{' || ch == '}') plain.append(ch);
                    } else if (ch == '\\') {
                        escaped = true;
                    } else if (ch == '{') {
                        depth++;
                    } else if (ch == '}') {
                        if (depth > 0) depth--;
                        plain.append(' ');
                    } else if (ch == '\r' || ch == '\n') {
                        plain.append(' ');
                    } else {
                        plain.append(ch);
                    }
                    if (plain.length() >= BUFFER_SIZE) {
                        if (matcher.feed(plain.toString())) return true;
                        plain.setLength(0);
                    }
                }
                return false;
            }

            private boolean finish() {
                return plain.length() > 0 && matcher.feed(plain.toString());
            }
        }

'''
text = text[:old_rtf_start] + rtf + text[old_rtf_end:]

source_path.write_text(text, encoding='utf-8')

pom = pom.replace('<version>1.2.0</version>\n    <name>简搜 PC</name>', '<version>1.2.3</version>\n    <name>简搜 PC</name>', 1)
pom = pom.replace('<finalName>simpletxtsearch-pc-1.2.0</finalName>', '<finalName>simpletxtsearch-pc-1.2.3</finalName>', 1)
pom_path.write_text(pom, encoding='utf-8')

print('Applied v1.2.3 content-search performance patch')
