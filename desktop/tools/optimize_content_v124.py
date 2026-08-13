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


replace_once('import org.apache.pdfbox.pdmodel.PDDocument;\n', 'import org.apache.pdfbox.io.MemoryUsageSetting;\nimport org.apache.pdfbox.pdmodel.PDDocument;\n')
replace_once('import java.io.BufferedReader;\n', 'import java.io.BufferedReader;\nimport java.io.ByteArrayInputStream;\n')
replace_once('import java.io.Reader;\n', 'import java.io.Reader;\nimport java.io.PushbackReader;\nimport java.io.SequenceInputStream;\n')
replace_once('import java.util.ArrayList;\n', 'import java.util.ArrayDeque;\nimport java.util.ArrayList;\n')
replace_once('import java.util.Arrays;\n', 'import java.util.Arrays;\nimport java.util.Deque;\n')

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
replace_once('        super("简搜 PC 1.2.0");\n', '        super("简搜 PC 1.2.4");\n')
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
                // Stream root entries: never materialize/sort the whole directory in memory.
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
                // Release the worker's temporary result references even on cancel/error.
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

            // ContentSearch owns and closes every parser/stream inside this call. No file body is retained here.
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
            currentPath = null;
            currentWorker = null;
        }
    }

'''
text = text[:start] + worker + text[end:]

# Replace plain text path so charset detection and content scanning share ONE disk stream.
old_plain_start = text.find('        private static boolean containsPlainText(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {')
old_plain_end = text.find('        private static boolean containsPdf(', old_plain_start)
if old_plain_start < 0 or old_plain_end < 0:
    raise SystemExit('Plain text section markers not found')
plain = r'''        private static boolean containsPlainText(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {
            try (InputStream input = new BufferedInputStream(Files.newInputStream(file), 64 * 1024)) {
                byte[] sample = input.readNBytes(64 * 1024);
                Charset charset = detectCharset(sample);
                try (InputStream replay = new SequenceInputStream(new ByteArrayInputStream(sample), input);
                     Reader reader = new BufferedReader(new InputStreamReader(replay, charset), BUFFER_SIZE * 2)) {
                    MultiMatcher matcher = new MultiMatcher(keywords, caseSensitive);
                    char[] buffer = new char[BUFFER_SIZE];
                    while (true) {
                        checkCancelled(cancelled);
                        int count = reader.read(buffer);
                        if (count < 0) return false;
                        if (count > 0 && matcher.feed(buffer, count)) return true;
                    }
                }
            }
        }

'''
text = text[:old_plain_start] + plain + text[old_plain_end:]

# Bound PDF parser heap usage; PDDocument.close() also deletes any PDFBox scratch temp resources immediately.
replace_once(
    '            try (PDDocument document = PDDocument.load(file.toFile())) {\n',
    '            try (PDDocument document = PDDocument.load(file.toFile(), MemoryUsageSetting.setupMixed(32L * 1024L * 1024L))) {\n'
)

# Stream legacy DOC paragraph-by-paragraph instead of extractor.getText() retaining the whole body string.
old_word_start = text.find('        private static boolean containsLegacyWord(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {')
old_word_end = text.find('        private static boolean containsLegacySpreadsheet(', old_word_start)
if old_word_start < 0 or old_word_end < 0:
    raise SystemExit('Legacy Word section markers not found')
word = r'''        private static boolean containsLegacyWord(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {
            checkCancelled(cancelled);
            MultiMatcher matcher = new MultiMatcher(keywords, caseSensitive);
            try (InputStream input = new BufferedInputStream(Files.newInputStream(file), 64 * 1024);
                 HWPFDocument document = new HWPFDocument(input)) {
                var range = document.getRange();
                for (int index = 0; index < range.numParagraphs(); index++) {
                    checkCancelled(cancelled);
                    if (matcher.feed(range.getParagraph(index).text()) || matcher.separator()) return true;
                }
            }
            return false;
        }

'''
text = text[:old_word_start] + word + text[old_word_end:]

# Always close XMLStreamReader, including early keyword matches.
old_zip_start = text.find('        private static boolean containsZipXml(Path file, String extension, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws Exception {')
old_zip_end = text.find('        private static void trySet(', old_zip_start)
if old_zip_start < 0 or old_zip_end < 0:
    raise SystemExit('Zip XML section markers not found')
zipxml = r'''        private static boolean containsZipXml(Path file, String extension, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws Exception {
            MultiMatcher matcher = new MultiMatcher(keywords, caseSensitive);
            XMLInputFactory factory = XMLInputFactory.newFactory();
            trySet(factory, XMLInputFactory.SUPPORT_DTD, false);
            trySet(factory, "javax.xml.stream.isSupportingExternalEntities", false);
            try (ZipInputStream zip = new ZipInputStream(new BufferedInputStream(Files.newInputStream(file), 64 * 1024))) {
                ZipEntry entry;
                while ((entry = zip.getNextEntry()) != null) {
                    checkCancelled(cancelled);
                    String name = entry.getName().toLowerCase(Locale.ROOT);
                    if (!entry.isDirectory() && isSearchableXmlEntry(extension, name)) {
                        XMLStreamReader reader = null;
                        try {
                            reader = factory.createXMLStreamReader(zip);
                            while (reader.hasNext()) {
                                checkCancelled(cancelled);
                                int event = reader.next();
                                if (event == XMLStreamConstants.CHARACTERS || event == XMLStreamConstants.CDATA) {
                                    if (matcher.feed(reader.getText())) return true;
                                } else if (event == XMLStreamConstants.END_ELEMENT
                                    && XML_BREAK_TAGS.contains(reader.getLocalName().toLowerCase(Locale.ROOT))
                                    && matcher.separator()) {
                                    return true;
                                }
                            }
                        } finally {
                            if (reader != null) {
                                try {
                                    reader.close();
                                } catch (Exception ignored) {
                                    // ZIP stream itself is closed by try-with-resources.
                                }
                            }
                        }
                        if (matcher.separator()) return true;
                    }
                    zip.closeEntry();
                }
            }
            return false;
        }

'''
text = text[:old_zip_start] + zipxml + text[old_zip_end:]

# True streaming RTF parser: no full raw RTF string + no full extracted text string retained together.
old_rtf_start = text.find('        private static boolean containsRtf(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {')
old_rtf_end = text.find('        private static Charset detectCharset(Path file) throws IOException {', old_rtf_start)
if old_rtf_start < 0 or old_rtf_end < 0:
    raise SystemExit('RTF section markers not found')
rtf = r'''        private static boolean containsRtf(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {
            MultiMatcher matcher = new MultiMatcher(keywords, caseSensitive);
            try (PushbackReader reader = new PushbackReader(
                new BufferedReader(Files.newBufferedReader(file, Charset.forName("windows-1252")), BUFFER_SIZE * 2), 4)) {
                Deque<Boolean> skipStack = new ArrayDeque<>();
                StringBuilder plain = new StringBuilder(BUFFER_SIZE);
                boolean skip = false;
                boolean pendingDestination = false;
                long consumed = 0;
                int code;
                while ((code = reader.read()) >= 0) {
                    if ((consumed++ & 4095L) == 0L) checkCancelled(cancelled);
                    char current = (char) code;
                    if (current == '{') {
                        skipStack.push(skip);
                    } else if (current == '}') {
                        skip = skipStack.isEmpty() ? false : skipStack.pop();
                        pendingDestination = false;
                        if (!skip) plain.append(' ');
                    } else if (current == '\\') {
                        int nextCode = reader.read();
                        if (nextCode < 0) break;
                        char next = (char) nextCode;
                        if (next == '\\' || next == '{' || next == '}') {
                            if (!skip) plain.append(next);
                        } else if (next == '*') {
                            pendingDestination = true;
                        } else if (next == '\'') {
                            int h1 = reader.read();
                            int h2 = reader.read();
                            if (h1 >= 0 && h2 >= 0 && !skip) {
                                try {
                                    plain.append((char) Integer.parseInt("" + (char) h1 + (char) h2, 16));
                                } catch (NumberFormatException ignored) {
                                    // Ignore malformed hex escape.
                                }
                            }
                        } else if (Character.isLetter(next)) {
                            StringBuilder wordBuilder = new StringBuilder(16);
                            wordBuilder.append(next);
                            int delimiter;
                            while ((delimiter = reader.read()) >= 0 && Character.isLetter((char) delimiter)) {
                                wordBuilder.append((char) delimiter);
                            }
                            String word = wordBuilder.toString().toLowerCase(Locale.ROOT);
                            StringBuilder numberBuilder = new StringBuilder(8);
                            if (delimiter == '-' || delimiter == '+') {
                                numberBuilder.append((char) delimiter);
                                delimiter = reader.read();
                            }
                            while (delimiter >= 0 && Character.isDigit((char) delimiter)) {
                                numberBuilder.append((char) delimiter);
                                delimiter = reader.read();
                            }
                            Integer number = null;
                            if (!numberBuilder.isEmpty() && !numberBuilder.toString().equals("+") && !numberBuilder.toString().equals("-")) {
                                try {
                                    number = Integer.valueOf(numberBuilder.toString());
                                } catch (NumberFormatException ignored) {
                                    // Ignore malformed numeric argument.
                                }
                            }
                            if (delimiter >= 0 && delimiter != ' ') reader.unread(delimiter);

                            if (pendingDestination || RTF_DESTINATIONS.contains(word)) {
                                skip = true;
                                pendingDestination = false;
                            } else if (!skip) {
                                switch (word) {
                                    case "par", "line" -> plain.append('\n');
                                    case "tab" -> plain.append('\t');
                                    case "u" -> {
                                        if (number != null) {
                                            plain.append((char) (number & 0xFFFF));
                                            int fallback = reader.read();
                                            if (fallback >= 0 && fallback == '\\') reader.unread(fallback);
                                        }
                                    }
                                    default -> {
                                    }
                                }
                            }
                        } else {
                            // One-character control symbol. It carries no searchable body text here.
                        }
                    } else if (current != '\r' && current != '\n' && !skip) {
                        plain.append(current);
                    }

                    if (plain.length() >= BUFFER_SIZE) {
                        if (matcher.feed(plain.toString())) return true;
                        plain.setLength(0);
                    }
                }
                return plain.length() > 0 && matcher.feed(plain.toString());
            }
        }

        private static Charset detectCharset(byte[] sample) {
            if (sample.length >= 3 && sample[0] == (byte) 0xEF && sample[1] == (byte) 0xBB && sample[2] == (byte) 0xBF) {
                return StandardCharsets.UTF_8;
            }
            if (sample.length >= 2 && sample[0] == (byte) 0xFF && sample[1] == (byte) 0xFE) {
                return StandardCharsets.UTF_16LE;
            }
            if (sample.length >= 2 && sample[0] == (byte) 0xFE && sample[1] == (byte) 0xFF) {
                return StandardCharsets.UTF_16BE;
            }
            UniversalDetector detector = new UniversalDetector(null);
            if (sample.length > 0) detector.handleData(sample, 0, sample.length);
            detector.dataEnd();
            String detected = detector.getDetectedCharset();
            detector.reset();
            if (detected == null || detected.isBlank()) return StandardCharsets.UTF_8;
            String normalized = switch (detected.toUpperCase(Locale.ROOT)) {
                case "GB2312", "GBK", "GB18030" -> "GB18030";
                case "UTF8" -> "UTF-8";
                default -> detected;
            };
            try {
                return Charset.forName(normalized);
            } catch (Exception ignored) {
                return StandardCharsets.UTF_8;
            }
        }

'''
text = text[:old_rtf_start] + rtf + text[old_rtf_end:]

# Remove now-obsolete detectCharset(Path) left after the new byte-sample overload insertion.
old_detect_start = text.find('        private static Charset detectCharset(Path file) throws IOException {')
old_detect_end = text.find('        private static String extension(Path file) {', old_detect_start)
if old_detect_start >= 0 and old_detect_end >= 0:
    text = text[:old_detect_start] + text[old_detect_end:]

# Replace MultiMatcher with a lower-allocation implementation. Each chunk is normalized ONCE, not once per keyword.
matcher_start = text.find('    private static final class MultiMatcher {')
if matcher_start < 0:
    raise SystemExit('MultiMatcher marker not found')
matcher = r'''    private static final class MultiMatcher {
        private final List<String> targets;
        private final boolean caseSensitive;
        private final boolean[] found;
        private final String[] tails;
        private final int[] overlaps;

        private MultiMatcher(List<String> keywords, boolean caseSensitive) {
            this.caseSensitive = caseSensitive;
            this.targets = keywords.stream().map(this::normalize).toList();
            this.found = new boolean[targets.size()];
            this.tails = new String[targets.size()];
            this.overlaps = new int[targets.size()];
            for (int index = 0; index < targets.size(); index++) {
                tails[index] = "";
                overlaps[index] = Math.max(0, targets.get(index).length() - 1);
            }
        }

        private boolean feed(char[] value, int count) {
            return feed(new String(value, 0, count));
        }

        private boolean feed(String value) {
            if (targets.isEmpty()) return false;
            String normalizedValue = normalize(value);
            for (int index = 0; index < targets.size(); index++) {
                if (found[index]) continue;
                String combined = tails[index] + normalizedValue;
                if (combined.contains(targets.get(index))) {
                    found[index] = true;
                    tails[index] = "";
                } else {
                    int overlap = overlaps[index];
                    tails[index] = overlap == 0 ? "" : combined.substring(Math.max(0, combined.length() - overlap));
                }
            }
            for (boolean valueFound : found) {
                if (!valueFound) return false;
            }
            return true;
        }

        private boolean separator() {
            return feed("\n");
        }

        private String normalize(String value) {
            return caseSensitive ? value : value.toLowerCase(Locale.ROOT);
        }
    }
}'''
text = text[:matcher_start] + matcher + '\n'

source_path.write_text(text, encoding='utf-8')

pom = pom.replace('<version>1.2.0</version>\n    <name>简搜 PC</name>', '<version>1.2.4</version>\n    <name>简搜 PC</name>', 1)
pom = pom.replace('<finalName>simpletxtsearch-pc-1.2.0</finalName>', '<finalName>simpletxtsearch-pc-1.2.4</finalName>', 1)
pom_path.write_text(pom, encoding='utf-8')

print('Applied v1.2.4 fast content search + deterministic resource cleanup patch')
