from pathlib import Path

source_path = Path('desktop/src/main/java/com/luxiaoshi/simpletxtsearch/pc/SimpleTxtSearchPc.java')
pom_path = Path('desktop/pom.xml')
text = source_path.read_text(encoding='utf-8')
pom = pom_path.read_text(encoding='utf-8')


def replace_once(old: str, new: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f'Expected source fragment not found: {old[:160]!r}')
    text = text.replace(old, new, 1)


replace_once(
    '    private static final int MAX_KEYWORDS = 10;\n',
    '''    private static final int MAX_KEYWORDS = 10;\n'''
    '''    private static final long MAX_CONTENT_FILE_SIZE_BYTES = 50L * 1024L * 1024L;\n'''
    '''    private static final int MAX_DISPLAY_RESULTS = 5000;\n'''
    '''    private static final int RESULT_BATCH_SIZE = 50;\n'''
    '''    private static final long STATUS_UPDATE_INTERVAL_NANOS = 250_000_000L;\n'''
    '''    private static final Set<String> CONTENT_TEXT_EXTENSIONS = Set.of(\n'''
    '''        "txt", "md", "log", "csv", "tsv", "json", "xml", "java", "py", "kt", "kts",\n'''
    '''        "js", "ts", "html", "htm", "css", "yaml", "yml", "ini", "conf", "properties"\n'''
    '''    );\n'''
    '''    private static final Set<String> EXCLUDED_DIRECTORY_NAMES = Set.of(\n'''
    '''        ".git", "node_modules", ".venv", "venv", "__pycache__", "runtime", "output",\n'''
    '''        "build", "dist", "target", "cache", "caches", "tmp", "temp", "缓存", "旧版", "过往不用"\n'''
    '''    );\n'''
)
replace_once('    private static final String PREF_TYPES = "types";\n', '    private static final String PREF_TYPES = "types";\n    private static final String PREF_CONTENT = "contentSearch";\n')
replace_once(
    '    private final JCheckBox caseSensitiveBox = new JCheckBox("区分大小写");\n',
    '    private final JCheckBox caseSensitiveBox = new JCheckBox("区分大小写");\n    private final JCheckBox contentSearchBox = new JCheckBox("搜索文件内容（较慢，仅文本白名单）", false);\n'
)
replace_once(
    '    private final JLabel statusLabel = new JLabel("请选择总文件夹并输入关键词");\n',
    '    private final JLabel statusLabel = new JLabel("请选择总文件夹并输入关键词");\n    private final JLabel currentPathLabel = new JLabel("当前：—");\n'
)
replace_once('        super("简搜 PC 1.2.0");\n', '        super("简搜 PC 1.2.2");\n')
replace_once(
    '        JLabel description = new JLabel("每个关键词用空格分隔，最多 10 个；文件中必须同时包含全部关键词才会匹配。双击结果可打开文件。");\n',
    '        JLabel description = new JLabel("默认只搜索文件名，不读取文件内容；如需内容搜索请单独勾选。多个关键词必须全部满足。");\n'
)
replace_once(
    '''        JPanel typePanel = new JPanel(new FlowLayout(FlowLayout.LEFT, 10, 0));\n        typePanel.add(txtBox);\n        typePanel.add(pdfBox);\n        typePanel.add(documentBox);\n        typePanel.add(spreadsheetBox);\n''',
    '''        JPanel typePanel = new JPanel(new FlowLayout(FlowLayout.LEFT, 10, 0));\n        typePanel.add(contentSearchBox);\n        JLabel contentHint = new JLabel("默认文件名搜索全部文件；内容模式仅扫描常见文本/代码文件，不扫描 PDF、Office、APK、JAR、EXE 等。");\n        typePanel.add(contentHint);\n'''
)
replace_once(
    '''        JPanel statusPanel = new JPanel(new BorderLayout());\n        statusPanel.setBorder(BorderFactory.createEmptyBorder(4, 4, 0, 4));\n        statusPanel.add(statusLabel, BorderLayout.CENTER);\n''',
    '''        JPanel statusPanel = new JPanel(new BorderLayout(0, 3));\n        statusPanel.setBorder(BorderFactory.createEmptyBorder(4, 4, 0, 4));\n        statusPanel.add(statusLabel, BorderLayout.NORTH);\n        currentPathLabel.setToolTipText("当前正在检查的文件路径");\n        statusPanel.add(currentPathLabel, BorderLayout.SOUTH);\n'''
)
replace_once(
    '        caseSensitiveBox.setSelected(preferences.getBoolean(PREF_CASE, false));\n',
    '        caseSensitiveBox.setSelected(preferences.getBoolean(PREF_CASE, false));\n        contentSearchBox.setSelected(preferences.getBoolean(PREF_CONTENT, false));\n'
)

old_start = '''        EnumSet<FileCategory> categories = selectedCategories();\n        if (categories.isEmpty()) {\n            JOptionPane.showMessageDialog(this, "请至少选择一种文件类型。", "无法开始", JOptionPane.WARNING_MESSAGE);\n            return;\n        }\n\n        savePreferences(categories);\n        resultModel.clear();\n        currentWorker = new SearchWorker(rootFolder, List.copyOf(selectedChildFolders), keywords, caseSensitiveBox.isSelected(), categories);\n        startButton.setEnabled(false);\n        stopButton.setEnabled(true);\n        statusLabel.setText("正在准备搜索……");\n        currentWorker.execute();\n'''
new_start = '''        savePreferences();\n        resultModel.clear();\n        currentPathLabel.setText("当前：准备扫描……");\n        currentWorker = new SearchWorker(\n            rootFolder,\n            List.copyOf(selectedChildFolders),\n            keywords,\n            caseSensitiveBox.isSelected(),\n            contentSearchBox.isSelected()\n        );\n        startButton.setEnabled(false);\n        stopButton.setEnabled(true);\n        statusLabel.setText(contentSearchBox.isSelected()\n            ? "正在准备内容搜索（仅文本白名单）……"\n            : "正在准备文件名搜索（不读取文件内容）……");\n        currentWorker.execute();\n'''
replace_once(old_start, new_start)

old_save = '''    private void savePreferences(EnumSet<FileCategory> categories) {\n        preferences.put(PREF_KEYWORDS, keywordField.getText().trim());\n        preferences.putBoolean(PREF_CASE, caseSensitiveBox.isSelected());\n        preferences.put(PREF_TYPES, categories.stream().map(Enum::name).sorted().reduce((left, right) -> left + "," + right).orElse(""));\n    }\n'''
new_save = '''    private void savePreferences() {\n        preferences.put(PREF_KEYWORDS, keywordField.getText().trim());\n        preferences.putBoolean(PREF_CASE, caseSensitiveBox.isSelected());\n        preferences.putBoolean(PREF_CONTENT, contentSearchBox.isSelected());\n    }\n'''
replace_once(old_save, new_save)

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
        private final boolean contentSearch;
        private final List<ResultItem> resultBatch = new ArrayList<>(RESULT_BATCH_SIZE);
        private int visited;
        private int contentRead;
        private int matched;
        private int failed;
        private int skippedLarge;
        private int skippedDirectories;
        private int skippedNonText;
        private int queuedForDisplay;
        private long lastStatusUpdateNanos;
        private Path currentPath;

        private SearchWorker(Path searchRoot, List<Path> selectedRoots, List<String> keywords, boolean caseSensitive, boolean contentSearch) {
            this.searchRoot = searchRoot;
            this.selectedRoots = selectedRoots;
            this.keywords = keywords;
            this.caseSensitive = caseSensitive;
            this.contentSearch = contentSearch;
        }

        @Override
        protected Void doInBackground() throws Exception {
            try {
                try (var stream = Files.newDirectoryStream(searchRoot)) {
                    for (Path entry : stream) {
                        checkCancelled();
                        if (Files.isRegularFile(entry)) inspectFile(entry, safeFileSize(entry));
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
                            if (attrs.isRegularFile()) inspectFile(file, attrs.size());
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

        private long safeFileSize(Path file) {
            try {
                return Files.size(file);
            } catch (IOException ignored) {
                return -1L;
            }
        }

        private void inspectFile(Path file, long fileSize) {
            checkCancelled();
            visited++;
            currentPath = file;
            boolean hit = false;

            if (!contentSearch) {
                hit = fileNameContainsAll(file, keywords, caseSensitive);
            } else {
                String extension = extensionOf(file);
                if (!CONTENT_TEXT_EXTENSIONS.contains(extension)) {
                    skippedNonText++;
                    updateStatus(false);
                    return;
                }
                if (fileSize > MAX_CONTENT_FILE_SIZE_BYTES) {
                    skippedLarge++;
                    updateStatus(false);
                    return;
                }
                try {
                    contentRead++;
                    hit = ContentSearch.contains(file, keywords, caseSensitive, this::isCancelled);
                } catch (CancellationException error) {
                    throw error;
                } catch (Exception error) {
                    failed++;
                }
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

        private boolean fileNameContainsAll(Path file, List<String> terms, boolean sensitive) {
            String name = file.getFileName() == null ? file.toString() : file.getFileName().toString();
            String haystack = sensitive ? name : name.toLowerCase(Locale.ROOT);
            for (String term : terms) {
                String needle = sensitive ? term : term.toLowerCase(Locale.ROOT);
                if (!haystack.contains(needle)) return false;
            }
            return true;
        }

        private String extensionOf(Path file) {
            String name = file.getFileName() == null ? "" : file.getFileName().toString();
            int dot = name.lastIndexOf('.');
            return dot < 0 || dot == name.length() - 1 ? "" : name.substring(dot + 1).toLowerCase(Locale.ROOT);
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
            int contentReadSnapshot = contentRead;
            int matchedSnapshot = matched;
            int failedSnapshot = failed;
            int largeSnapshot = skippedLarge;
            int directorySnapshot = skippedDirectories;
            int nonTextSnapshot = skippedNonText;
            Path pathSnapshot = currentPath;
            boolean modeSnapshot = contentSearch;

            SwingUtilities.invokeLater(() -> {
                if (currentWorker != this) return;
                StringBuilder status = new StringBuilder(modeSnapshot ? "内容搜索：" : "文件名搜索：")
                    .append("已检查 ").append(visitedSnapshot).append(" 个文件");
                if (modeSnapshot) status.append("，实际读取内容 ").append(contentReadSnapshot).append(" 个");
                status.append("，找到 ").append(matchedSnapshot).append(" 个");
                if (matchedSnapshot > MAX_DISPLAY_RESULTS) {
                    status.append("（界面仅显示前 ").append(MAX_DISPLAY_RESULTS).append(" 个，扫描继续）");
                }
                if (directorySnapshot > 0) status.append("，排除目录 ").append(directorySnapshot).append(" 个");
                if (modeSnapshot && nonTextSnapshot > 0) status.append("，非文本跳过 ").append(nonTextSnapshot).append(" 个");
                if (largeSnapshot > 0) status.append("，超 50 MB 跳过 ").append(largeSnapshot).append(" 个");
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
            String mode = contentSearch ? "内容搜索" : "文件名搜索";
            String displaySuffix = matched > MAX_DISPLAY_RESULTS ? "；界面仅保留前 " + MAX_DISPLAY_RESULTS + " 个结果" : "";
            String skipSuffix = (skippedDirectories > 0 ? "，排除目录 " + skippedDirectories + " 个" : "")
                + (contentSearch && skippedNonText > 0 ? "，非文本跳过 " + skippedNonText + " 个" : "")
                + (skippedLarge > 0 ? "，超 50 MB 跳过 " + skippedLarge + " 个" : "")
                + (failed > 0 ? "，读取失败 " + failed + " 个" : "");
            String readSuffix = contentSearch ? "，实际读取内容 " + contentRead + " 个" : "";
            if (isCancelled()) {
                statusLabel.setText(mode + "已停止：已检查 " + visited + " 个文件" + readSuffix + "，找到 " + matched + " 个" + skipSuffix + displaySuffix);
            } else {
                try {
                    get();
                    statusLabel.setText(mode + "完成：已检查 " + visited + " 个文件" + readSuffix + "，找到 " + matched + " 个" + skipSuffix + displaySuffix);
                    currentPathLabel.setText("当前：扫描完成");
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

old_plain = '''        private static boolean containsPlainText(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {\n            Charset charset = detectCharset(file);\n            try (Reader reader = Files.newBufferedReader(file, charset)) {\n                MultiMatcher matcher = new MultiMatcher(keywords, caseSensitive);\n                char[] buffer = new char[BUFFER_SIZE];\n                while (true) {\n                    checkCancelled(cancelled);\n                    int count = reader.read(buffer);\n                    if (count < 0) return false;\n                    if (count > 0 && matcher.feed(new String(buffer, 0, count))) return true;\n                }\n            }\n        }\n'''
new_plain = '''        private static boolean containsPlainText(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {\n            Charset charset = detectCharset(file);\n            MultiMatcher matcher = new MultiMatcher(keywords, caseSensitive);\n            try (BufferedReader reader = Files.newBufferedReader(file, charset)) {\n                String line;\n                while ((line = reader.readLine()) != null) {\n                    checkCancelled(cancelled);\n                    if (matcher.feed(line) || matcher.separator()) return true;\n                }\n            }\n            return false;\n        }\n'''
replace_once(old_plain, new_plain)
replace_once(
    '                case "txt", "md", "log", "csv", "tsv" -> containsPlainText(file, keywords, caseSensitive, cancelled);\n',
    '                case "txt", "md", "log", "csv", "tsv", "json", "xml", "java", "py", "kt", "kts", "js", "ts", "html", "htm", "css", "yaml", "yml", "ini", "conf", "properties" -> containsPlainText(file, keywords, caseSensitive, cancelled);\n'
)

source_path.write_text(text, encoding='utf-8')

pom = pom.replace('<version>1.2.0</version>\n    <name>简搜 PC</name>', '<version>1.2.2</version>\n    <name>简搜 PC</name>', 1)
pom = pom.replace('<finalName>simpletxtsearch-pc-1.2.0</finalName>', '<finalName>simpletxtsearch-pc-1.2.2</finalName>', 1)
if '<version>1.2.2</version>' not in pom or 'simpletxtsearch-pc-1.2.2' not in pom:
    raise SystemExit('POM version update failed')
pom_path.write_text(pom, encoding='utf-8')

print(f'Patched {source_path} and {pom_path} for v1.2.2')
