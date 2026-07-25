package com.luxiaoshi.simpletxtsearch.pc;

import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.poi.hssf.usermodel.HSSFWorkbook;
import org.apache.poi.hwpf.HWPFDocument;
import org.apache.poi.hwpf.extractor.WordExtractor;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.DataFormatter;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.mozilla.universalchardet.UniversalDetector;

import javax.swing.BorderFactory;
import javax.swing.DefaultListModel;
import javax.swing.JButton;
import javax.swing.JCheckBox;
import javax.swing.JFileChooser;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JList;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JSplitPane;
import javax.swing.JTextField;
import javax.swing.ListSelectionModel;
import javax.swing.SwingUtilities;
import javax.swing.SwingWorker;
import javax.swing.UIManager;
import javax.xml.stream.XMLInputFactory;
import javax.xml.stream.XMLStreamConstants;
import javax.xml.stream.XMLStreamReader;
import java.awt.BorderLayout;
import java.awt.Desktop;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Font;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
import java.awt.Toolkit;
import java.awt.datatransfer.StringSelection;
import java.awt.event.MouseAdapter;
import java.awt.event.MouseEvent;
import java.io.BufferedInputStream;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.CancellationException;
import java.util.function.BooleanSupplier;
import java.util.prefs.Preferences;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public final class SimpleTxtSearchPc extends JFrame {
    private static final int MAX_KEYWORDS = 10;
    private static final String PREF_ROOT = "root";
    private static final String PREF_KEYWORDS = "keywords";
    private static final String PREF_CASE = "caseSensitive";
    private static final String PREF_TYPES = "types";

    private final Preferences preferences = Preferences.userNodeForPackage(SimpleTxtSearchPc.class);
    private final JTextField folderField = new JTextField();
    private final JTextField keywordField = new JTextField();
    private final JCheckBox caseSensitiveBox = new JCheckBox("区分大小写");
    private final JCheckBox txtBox = new JCheckBox("TXT（txt、md、log）", true);
    private final JCheckBox pdfBox = new JCheckBox("PDF", true);
    private final JCheckBox documentBox = new JCheckBox("文档（doc、docx、odt、rtf）", true);
    private final JCheckBox spreadsheetBox = new JCheckBox("表格（xls、xlsx、ods、csv、tsv）", true);
    private final JLabel rangeLabel = new JLabel("搜索范围：尚未选择总文件夹");
    private final JLabel statusLabel = new JLabel("请选择总文件夹并输入关键词");
    private final DefaultListModel<ResultItem> resultModel = new DefaultListModel<>();
    private final JList<ResultItem> resultList = new JList<>(resultModel);
    private final JButton chooseChildrenButton = new JButton("选择参与搜索的一级子文件夹");
    private final JButton startButton = new JButton("开始搜索");
    private final JButton stopButton = new JButton("停止");

    private Path rootFolder;
    private List<Path> childFolders = List.of();
    private final Set<Path> selectedChildFolders = new LinkedHashSet<>();
    private SearchWorker currentWorker;

    private SimpleTxtSearchPc() {
        super("简搜 PC 1.2.0");
        setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        setMinimumSize(new Dimension(920, 650));
        setSize(1080, 760);
        setLocationRelativeTo(null);
        buildUi();
        restorePreferences();
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> {
            try {
                UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName());
            } catch (Exception ignored) {
                // 使用默认外观。
            }
            new SimpleTxtSearchPc().setVisible(true);
        });
    }

    private void buildUi() {
        JPanel root = new JPanel(new BorderLayout(10, 10));
        root.setBorder(BorderFactory.createEmptyBorder(14, 14, 14, 14));
        setContentPane(root);

        JLabel title = new JLabel("简搜");
        title.setFont(title.getFont().deriveFont(Font.BOLD, 26f));
        JLabel description = new JLabel("每个关键词用空格分隔，最多 10 个；文件中必须同时包含全部关键词才会匹配。双击结果可打开文件。");

        JPanel header = new JPanel(new BorderLayout(0, 5));
        header.add(title, BorderLayout.NORTH);
        header.add(description, BorderLayout.CENTER);
        root.add(header, BorderLayout.NORTH);

        JPanel settings = new JPanel(new GridBagLayout());
        settings.setBorder(BorderFactory.createTitledBorder("搜索设置"));
        GridBagConstraints c = new GridBagConstraints();
        c.insets = new Insets(5, 5, 5, 5);
        c.fill = GridBagConstraints.HORIZONTAL;
        c.weightx = 0;
        c.gridx = 0;
        c.gridy = 0;
        settings.add(new JLabel("总文件夹"), c);

        folderField.setEditable(false);
        c.gridx = 1;
        c.weightx = 1;
        settings.add(folderField, c);
        JButton chooseFolderButton = new JButton("选择总文件夹");
        chooseFolderButton.addActionListener(event -> chooseRootFolder());
        c.gridx = 2;
        c.weightx = 0;
        settings.add(chooseFolderButton, c);

        chooseChildrenButton.setEnabled(false);
        chooseChildrenButton.addActionListener(event -> chooseChildFolders());
        c.gridx = 1;
        c.gridy = 1;
        c.gridwidth = 2;
        settings.add(chooseChildrenButton, c);

        c.gridy = 2;
        settings.add(rangeLabel, c);

        c.gridx = 0;
        c.gridy = 3;
        c.gridwidth = 1;
        settings.add(new JLabel("关键词"), c);
        keywordField.setToolTipText("例：森林 分解 质量；最多 10 个关键词");
        c.gridx = 1;
        c.weightx = 1;
        settings.add(keywordField, c);
        c.gridx = 2;
        c.weightx = 0;
        settings.add(caseSensitiveBox, c);

        JPanel typePanel = new JPanel(new FlowLayout(FlowLayout.LEFT, 10, 0));
        typePanel.add(txtBox);
        typePanel.add(pdfBox);
        typePanel.add(documentBox);
        typePanel.add(spreadsheetBox);
        c.gridx = 1;
        c.gridy = 4;
        c.gridwidth = 2;
        settings.add(typePanel, c);

        JPanel actions = new JPanel(new FlowLayout(FlowLayout.LEFT, 8, 0));
        startButton.addActionListener(event -> startSearch());
        stopButton.setEnabled(false);
        stopButton.addActionListener(event -> stopSearch());
        JButton openButton = new JButton("打开所选文件");
        openButton.addActionListener(event -> openSelectedResult());
        JButton openFolderButton = new JButton("打开所在文件夹");
        openFolderButton.addActionListener(event -> openSelectedFolder());
        JButton copyButton = new JButton("复制文件名");
        copyButton.addActionListener(event -> copyResultNames());
        actions.add(startButton);
        actions.add(stopButton);
        actions.add(openButton);
        actions.add(openFolderButton);
        actions.add(copyButton);
        c.gridy = 5;
        settings.add(actions, c);

        resultList.setSelectionMode(ListSelectionModel.SINGLE_SELECTION);
        resultList.setFont(resultList.getFont().deriveFont(15f));
        resultList.addMouseListener(new MouseAdapter() {
            @Override
            public void mouseClicked(MouseEvent event) {
                if (event.getClickCount() == 2) openSelectedResult();
            }
        });
        JScrollPane resultScroll = new JScrollPane(resultList);
        resultScroll.setBorder(BorderFactory.createTitledBorder("匹配文件"));

        JPanel statusPanel = new JPanel(new BorderLayout());
        statusPanel.setBorder(BorderFactory.createEmptyBorder(4, 4, 0, 4));
        statusPanel.add(statusLabel, BorderLayout.CENTER);

        JPanel lower = new JPanel(new BorderLayout(0, 7));
        lower.add(resultScroll, BorderLayout.CENTER);
        lower.add(statusPanel, BorderLayout.SOUTH);

        JSplitPane splitPane = new JSplitPane(JSplitPane.VERTICAL_SPLIT, settings, lower);
        splitPane.setResizeWeight(0.35);
        splitPane.setDividerLocation(270);
        splitPane.setBorder(null);
        root.add(splitPane, BorderLayout.CENTER);
    }

    private void restorePreferences() {
        keywordField.setText(preferences.get(PREF_KEYWORDS, ""));
        caseSensitiveBox.setSelected(preferences.getBoolean(PREF_CASE, false));
        Set<String> types = parseSavedTypes(preferences.get(PREF_TYPES, "TXT,PDF,DOCUMENT,SPREADSHEET"));
        txtBox.setSelected(types.contains(FileCategory.TXT.name()));
        pdfBox.setSelected(types.contains(FileCategory.PDF.name()));
        documentBox.setSelected(types.contains(FileCategory.DOCUMENT.name()));
        spreadsheetBox.setSelected(types.contains(FileCategory.SPREADSHEET.name()));

        String savedRoot = preferences.get(PREF_ROOT, "");
        if (!savedRoot.isBlank()) {
            Path candidate = Path.of(savedRoot);
            if (Files.isDirectory(candidate)) setRootFolder(candidate, false);
        }
    }

    private Set<String> parseSavedTypes(String value) {
        Set<String> result = new LinkedHashSet<>();
        Arrays.stream(value.split(","))
            .map(String::trim)
            .filter(item -> !item.isEmpty())
            .forEach(result::add);
        return result;
    }

    private void chooseRootFolder() {
        JFileChooser chooser = new JFileChooser(rootFolder == null ? null : rootFolder.toFile());
        chooser.setDialogTitle("选择总文件夹");
        chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY);
        chooser.setAcceptAllFileFilterUsed(false);
        if (chooser.showOpenDialog(this) == JFileChooser.APPROVE_OPTION) {
            setRootFolder(chooser.getSelectedFile().toPath(), true);
        }
    }

    private void setRootFolder(Path folder, boolean showChildrenDialog) {
        rootFolder = folder.toAbsolutePath().normalize();
        folderField.setText(rootFolder.toString());
        preferences.put(PREF_ROOT, rootFolder.toString());
        try {
            List<Path> folders = new ArrayList<>();
            try (var stream = Files.list(rootFolder)) {
                stream.filter(Files::isDirectory)
                    .sorted(Comparator.comparing(path -> path.getFileName().toString().toLowerCase(Locale.ROOT)))
                    .forEach(folders::add);
            }
            childFolders = List.copyOf(folders);
            selectedChildFolders.clear();
            selectedChildFolders.addAll(childFolders);
            chooseChildrenButton.setEnabled(!childFolders.isEmpty());
            updateRangeLabel();
            if (showChildrenDialog && !childFolders.isEmpty()) chooseChildFolders();
        } catch (IOException error) {
            showError("无法读取总文件夹", error);
        }
    }

    private void chooseChildFolders() {
        if (childFolders.isEmpty()) {
            JOptionPane.showMessageDialog(this, "该总文件夹下没有一级子文件夹，将只搜索根目录文件。", "提示", JOptionPane.INFORMATION_MESSAGE);
            return;
        }
        JPanel panel = new JPanel();
        panel.setLayout(new javax.swing.BoxLayout(panel, javax.swing.BoxLayout.Y_AXIS));
        panel.add(new JLabel("默认全选。取消后，该一级子文件夹及其全部后代都不会参与搜索。根目录文件始终参与。"));
        List<JCheckBox> checks = new ArrayList<>();
        for (Path folder : childFolders) {
            JCheckBox check = new JCheckBox(folder.getFileName().toString(), selectedChildFolders.contains(folder));
            checks.add(check);
            panel.add(check);
        }
        JScrollPane scrollPane = new JScrollPane(panel);
        scrollPane.setPreferredSize(new Dimension(560, Math.min(420, 70 + childFolders.size() * 28)));
        int choice = JOptionPane.showConfirmDialog(this, scrollPane, "选择参与搜索的一级子文件夹", JOptionPane.OK_CANCEL_OPTION, JOptionPane.PLAIN_MESSAGE);
        if (choice == JOptionPane.OK_OPTION) {
            selectedChildFolders.clear();
            for (int index = 0; index < checks.size(); index++) {
                if (checks.get(index).isSelected()) selectedChildFolders.add(childFolders.get(index));
            }
            updateRangeLabel();
        }
    }

    private void updateRangeLabel() {
        if (rootFolder == null) {
            rangeLabel.setText("搜索范围：尚未选择总文件夹");
        } else if (childFolders.isEmpty()) {
            rangeLabel.setText("搜索范围：总文件夹根目录");
        } else {
            int excluded = childFolders.size() - selectedChildFolders.size();
            rangeLabel.setText("搜索范围：根目录 + 已选 " + selectedChildFolders.size() + "/" + childFolders.size()
                + " 个一级子文件夹" + (excluded > 0 ? "（已排除 " + excluded + " 个）" : ""));
        }
    }

    private void startSearch() {
        if (rootFolder == null || !Files.isDirectory(rootFolder)) {
            JOptionPane.showMessageDialog(this, "请先选择总文件夹。", "无法开始", JOptionPane.WARNING_MESSAGE);
            return;
        }
        List<String> keywords;
        try {
            keywords = parseKeywords(keywordField.getText());
        } catch (IllegalArgumentException error) {
            JOptionPane.showMessageDialog(this, error.getMessage(), "关键词不符合要求", JOptionPane.WARNING_MESSAGE);
            return;
        }
        EnumSet<FileCategory> categories = selectedCategories();
        if (categories.isEmpty()) {
            JOptionPane.showMessageDialog(this, "请至少选择一种文件类型。", "无法开始", JOptionPane.WARNING_MESSAGE);
            return;
        }

        savePreferences(categories);
        resultModel.clear();
        currentWorker = new SearchWorker(rootFolder, List.copyOf(selectedChildFolders), keywords, caseSensitiveBox.isSelected(), categories);
        startButton.setEnabled(false);
        stopButton.setEnabled(true);
        statusLabel.setText("正在准备搜索……");
        currentWorker.execute();
    }

    private List<String> parseKeywords(String raw) {
        List<String> tokens = Arrays.stream(raw.trim().split("\\s+"))
            .filter(item -> !item.isBlank())
            .distinct()
            .toList();
        if (tokens.isEmpty()) throw new IllegalArgumentException("请输入至少 1 个关键词。");
        if (tokens.size() > MAX_KEYWORDS) throw new IllegalArgumentException("关键词最多 " + MAX_KEYWORDS + " 个，请用空格分隔。");
        return tokens;
    }

    private EnumSet<FileCategory> selectedCategories() {
        EnumSet<FileCategory> result = EnumSet.noneOf(FileCategory.class);
        if (txtBox.isSelected()) result.add(FileCategory.TXT);
        if (pdfBox.isSelected()) result.add(FileCategory.PDF);
        if (documentBox.isSelected()) result.add(FileCategory.DOCUMENT);
        if (spreadsheetBox.isSelected()) result.add(FileCategory.SPREADSHEET);
        return result;
    }

    private void savePreferences(EnumSet<FileCategory> categories) {
        preferences.put(PREF_KEYWORDS, keywordField.getText().trim());
        preferences.putBoolean(PREF_CASE, caseSensitiveBox.isSelected());
        preferences.put(PREF_TYPES, categories.stream().map(Enum::name).sorted().reduce((left, right) -> left + "," + right).orElse(""));
    }

    private void stopSearch() {
        SearchWorker worker = currentWorker;
        if (worker != null) worker.cancel(true);
    }

    private void openSelectedResult() {
        ResultItem item = resultList.getSelectedValue();
        if (item == null) {
            JOptionPane.showMessageDialog(this, "请先选择一个搜索结果。", "提示", JOptionPane.INFORMATION_MESSAGE);
            return;
        }
        openPath(item.path());
    }

    private void openSelectedFolder() {
        ResultItem item = resultList.getSelectedValue();
        if (item == null) {
            JOptionPane.showMessageDialog(this, "请先选择一个搜索结果。", "提示", JOptionPane.INFORMATION_MESSAGE);
            return;
        }
        Path parent = item.path().getParent();
        if (parent != null) openPath(parent);
    }

    private void openPath(Path path) {
        if (!Desktop.isDesktopSupported()) {
            JOptionPane.showMessageDialog(this, "当前系统不支持直接打开文件。", "打开失败", JOptionPane.ERROR_MESSAGE);
            return;
        }
        try {
            Desktop.getDesktop().open(path.toFile());
        } catch (IOException error) {
            showError("无法打开：" + path, error);
        }
    }

    private void copyResultNames() {
        if (resultModel.isEmpty()) {
            JOptionPane.showMessageDialog(this, "当前没有匹配文件。", "提示", JOptionPane.INFORMATION_MESSAGE);
            return;
        }
        StringBuilder text = new StringBuilder();
        for (int index = 0; index < resultModel.size(); index++) {
            if (index > 0) text.append(System.lineSeparator());
            text.append(resultModel.get(index).path().getFileName());
        }
        Toolkit.getDefaultToolkit().getSystemClipboard().setContents(new StringSelection(text.toString()), null);
        statusLabel.setText("已复制 " + resultModel.size() + " 个文件名");
    }

    private void showError(String title, Throwable error) {
        JOptionPane.showMessageDialog(this, title + "\n" + (error.getMessage() == null ? error.getClass().getSimpleName() : error.getMessage()), "错误", JOptionPane.ERROR_MESSAGE);
    }

    private final class SearchWorker extends SwingWorker<Void, ResultItem> {
        private final Path searchRoot;
        private final List<Path> selectedRoots;
        private final List<String> keywords;
        private final boolean caseSensitive;
        private final EnumSet<FileCategory> categories;
        private int scanned;
        private int matched;
        private int failed;

        private SearchWorker(Path searchRoot, List<Path> selectedRoots, List<String> keywords, boolean caseSensitive, EnumSet<FileCategory> categories) {
            this.searchRoot = searchRoot;
            this.selectedRoots = selectedRoots;
            this.keywords = keywords;
            this.caseSensitive = caseSensitive;
            this.categories = categories;
        }

        @Override
        protected Void doInBackground() throws Exception {
            try (var stream = Files.list(searchRoot)) {
                for (Path entry : stream.filter(Files::isRegularFile).sorted().toList()) scanFile(entry);
            }
            for (Path selected : selectedRoots) {
                checkCancelled();
                Files.walkFileTree(selected, new SimpleFileVisitor<>() {
                    @Override
                    public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                        checkCancelled();
                        if (attrs.isRegularFile()) scanFile(file);
                        return FileVisitResult.CONTINUE;
                    }

                    @Override
                    public FileVisitResult visitFileFailed(Path file, IOException exc) {
                        failed++;
                        updateStatus();
                        return FileVisitResult.CONTINUE;
                    }
                });
            }
            return null;
        }

        private void scanFile(Path file) {
            checkCancelled();
            FileCategory category = FileCategory.from(file);
            if (category == null || !categories.contains(category)) return;
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
                publish(new ResultItem(file));
            }
            updateStatus();
        }

        private void updateStatus() {
            int scannedSnapshot = scanned;
            int matchedSnapshot = matched;
            int failedSnapshot = failed;
            SwingUtilities.invokeLater(() -> statusLabel.setText("正在搜索：已扫描 " + scannedSnapshot + " 个文件，找到 " + matchedSnapshot
                + " 个" + (failedSnapshot > 0 ? "，跳过 " + failedSnapshot + " 个无法读取的文件" : "")));
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
            if (isCancelled()) {
                statusLabel.setText("搜索已停止：已扫描 " + scanned + " 个文件，找到 " + matched + " 个");
            } else {
                try {
                    get();
                    statusLabel.setText("搜索完成：已扫描 " + scanned + " 个文件，找到 " + matched + " 个"
                        + (failed > 0 ? "，跳过 " + failed + " 个无法读取的文件" : ""));
                } catch (Exception error) {
                    statusLabel.setText("搜索失败：" + (error.getCause() == null ? error.getMessage() : error.getCause().getMessage()));
                }
            }
            currentWorker = null;
        }
    }

    private enum FileCategory {
        TXT(Set.of("txt", "md", "log")),
        PDF(Set.of("pdf")),
        DOCUMENT(Set.of("doc", "docx", "odt", "rtf")),
        SPREADSHEET(Set.of("xls", "xlsx", "ods", "csv", "tsv"));

        private final Set<String> extensions;

        FileCategory(Set<String> extensions) {
            this.extensions = extensions;
        }

        static FileCategory from(Path file) {
            String name = file.getFileName().toString();
            int dot = name.lastIndexOf('.');
            if (dot < 0 || dot == name.length() - 1) return null;
            String extension = name.substring(dot + 1).toLowerCase(Locale.ROOT);
            for (FileCategory category : values()) {
                if (category.extensions.contains(extension)) return category;
            }
            return null;
        }
    }

    private record ResultItem(Path path) {
        @Override
        public String toString() {
            return path.getFileName() + "    " + path;
        }
    }

    private static final class ContentSearch {
        private static final int BUFFER_SIZE = 8192;
        private static final Set<String> XML_BREAK_TAGS = Set.of("p", "br", "tr", "row", "c", "si", "t", "table-row", "table-cell");
        private static final Set<String> RTF_DESTINATIONS = Set.of(
            "fonttbl", "colortbl", "stylesheet", "info", "pict", "object", "header", "footer",
            "filetbl", "listtable", "listoverridetable", "generator", "xmlnstbl", "datastore"
        );

        private ContentSearch() {
        }

        static boolean contains(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws Exception {
            String extension = extension(file);
            return switch (extension) {
                case "txt", "md", "log", "csv", "tsv" -> containsPlainText(file, keywords, caseSensitive, cancelled);
                case "pdf" -> containsPdf(file, keywords, caseSensitive, cancelled);
                case "doc" -> containsLegacyWord(file, keywords, caseSensitive, cancelled);
                case "xls" -> containsLegacySpreadsheet(file, keywords, caseSensitive, cancelled);
                case "docx", "xlsx", "odt", "ods" -> containsZipXml(file, extension, keywords, caseSensitive, cancelled);
                case "rtf" -> containsRtf(file, keywords, caseSensitive, cancelled);
                default -> false;
            };
        }

        private static boolean containsPlainText(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {
            Charset charset = detectCharset(file);
            try (Reader reader = Files.newBufferedReader(file, charset)) {
                MultiMatcher matcher = new MultiMatcher(keywords, caseSensitive);
                char[] buffer = new char[BUFFER_SIZE];
                while (true) {
                    checkCancelled(cancelled);
                    int count = reader.read(buffer);
                    if (count < 0) return false;
                    if (count > 0 && matcher.feed(new String(buffer, 0, count))) return true;
                }
            }
        }

        private static boolean containsPdf(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {
            MultiMatcher matcher = new MultiMatcher(keywords, caseSensitive);
            try (PDDocument document = PDDocument.load(file.toFile())) {
                PDFTextStripper stripper = new PDFTextStripper();
                for (int page = 1; page <= document.getNumberOfPages(); page++) {
                    checkCancelled(cancelled);
                    stripper.setStartPage(page);
                    stripper.setEndPage(page);
                    if (matcher.feed(stripper.getText(document)) || matcher.separator()) return true;
                }
            }
            return false;
        }

        private static boolean containsLegacyWord(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {
            checkCancelled(cancelled);
            try (InputStream input = Files.newInputStream(file);
                 HWPFDocument document = new HWPFDocument(input);
                 WordExtractor extractor = new WordExtractor(document)) {
                return new MultiMatcher(keywords, caseSensitive).feed(extractor.getText());
            }
        }

        private static boolean containsLegacySpreadsheet(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {
            MultiMatcher matcher = new MultiMatcher(keywords, caseSensitive);
            try (InputStream input = Files.newInputStream(file); HSSFWorkbook workbook = new HSSFWorkbook(input)) {
                DataFormatter formatter = new DataFormatter();
                for (int sheetIndex = 0; sheetIndex < workbook.getNumberOfSheets(); sheetIndex++) {
                    checkCancelled(cancelled);
                    Sheet sheet = workbook.getSheetAt(sheetIndex);
                    if (matcher.feed(sheet.getSheetName()) || matcher.separator()) return true;
                    for (Row row : sheet) {
                        checkCancelled(cancelled);
                        for (Cell cell : row) {
                            if (matcher.feed(formatter.formatCellValue(cell)) || matcher.separator()) return true;
                        }
                    }
                }
            }
            return false;
        }

        private static boolean containsZipXml(Path file, String extension, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws Exception {
            MultiMatcher matcher = new MultiMatcher(keywords, caseSensitive);
            XMLInputFactory factory = XMLInputFactory.newFactory();
            trySet(factory, XMLInputFactory.SUPPORT_DTD, false);
            trySet(factory, "javax.xml.stream.isSupportingExternalEntities", false);
            try (ZipInputStream zip = new ZipInputStream(new BufferedInputStream(Files.newInputStream(file)))) {
                ZipEntry entry;
                while ((entry = zip.getNextEntry()) != null) {
                    checkCancelled(cancelled);
                    String name = entry.getName().toLowerCase(Locale.ROOT);
                    if (!entry.isDirectory() && isSearchableXmlEntry(extension, name)) {
                        XMLStreamReader reader = factory.createXMLStreamReader(zip);
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
                        reader.close();
                        if (matcher.separator()) return true;
                    }
                    zip.closeEntry();
                }
            }
            return false;
        }

        private static void trySet(XMLInputFactory factory, String property, Object value) {
            try {
                factory.setProperty(property, value);
            } catch (IllegalArgumentException ignored) {
                // 部分 JRE 不支持该属性。
            }
        }

        private static boolean isSearchableXmlEntry(String extension, String entryName) {
            return switch (extension) {
                case "docx" -> entryName.equals("word/document.xml")
                    || entryName.startsWith("word/header")
                    || entryName.startsWith("word/footer")
                    || Set.of("word/footnotes.xml", "word/endnotes.xml", "word/comments.xml").contains(entryName);
                case "xlsx" -> entryName.equals("xl/sharedstrings.xml")
                    || entryName.startsWith("xl/worksheets/")
                    || entryName.startsWith("xl/comments");
                case "odt", "ods" -> entryName.equals("content.xml");
                default -> false;
            };
        }

        private static boolean containsRtf(Path file, List<String> keywords, boolean caseSensitive, BooleanSupplier cancelled) throws IOException {
            String raw;
            try (BufferedReader reader = Files.newBufferedReader(file, Charset.forName("windows-1252"))) {
                StringBuilder builder = new StringBuilder();
                char[] buffer = new char[BUFFER_SIZE];
                int count;
                while ((count = reader.read(buffer)) >= 0) {
                    checkCancelled(cancelled);
                    if (count > 0) builder.append(buffer, 0, count);
                }
                raw = builder.toString();
            }
            return new MultiMatcher(keywords, caseSensitive).feed(extractRtfText(raw, cancelled));
        }

        private static String extractRtfText(String raw, BooleanSupplier cancelled) {
            StringBuilder output = new StringBuilder(Math.min(raw.length(), 1024 * 1024));
            List<Boolean> skipStack = new ArrayList<>();
            boolean skip = false;
            boolean pendingDestination = false;
            int index = 0;
            while (index < raw.length()) {
                if (index % 4096 == 0) checkCancelled(cancelled);
                char current = raw.charAt(index);
                if (current == '{') {
                    skipStack.add(skip);
                    index++;
                } else if (current == '}') {
                    skip = skipStack.isEmpty() ? false : skipStack.remove(skipStack.size() - 1);
                    pendingDestination = false;
                    index++;
                } else if (current == '\\') {
                    index++;
                    if (index >= raw.length()) break;
                    char next = raw.charAt(index);
                    if (next == '\\' || next == '{' || next == '}') {
                        if (!skip) output.append(next);
                        index++;
                    } else if (next == '*') {
                        pendingDestination = true;
                        index++;
                    } else if (next == '\'') {
                        if (index + 2 < raw.length()) {
                            try {
                                int value = Integer.parseInt(raw.substring(index + 1, index + 3), 16);
                                if (!skip) output.append((char) value);
                            } catch (NumberFormatException ignored) {
                                // 忽略损坏的十六进制转义。
                            }
                            index += 3;
                        } else {
                            index = raw.length();
                        }
                    } else {
                        int wordStart = index;
                        while (index < raw.length() && Character.isLetter(raw.charAt(index))) index++;
                        String word = raw.substring(wordStart, index).toLowerCase(Locale.ROOT);
                        int numberStart = index;
                        if (index < raw.length() && (raw.charAt(index) == '-' || raw.charAt(index) == '+')) index++;
                        while (index < raw.length() && Character.isDigit(raw.charAt(index))) index++;
                        Integer number = null;
                        try {
                            if (index > numberStart) number = Integer.valueOf(raw.substring(numberStart, index));
                        } catch (NumberFormatException ignored) {
                            // 忽略错误数值。
                        }
                        if (index < raw.length() && raw.charAt(index) == ' ') index++;
                        if (pendingDestination || RTF_DESTINATIONS.contains(word)) {
                            skip = true;
                            pendingDestination = false;
                        } else if (!skip) {
                            switch (word) {
                                case "par", "line" -> output.append('\n');
                                case "tab" -> output.append('\t');
                                case "u" -> {
                                    if (number != null) {
                                        output.append((char) (number & 0xFFFF));
                                        if (index < raw.length() && "\\{}".indexOf(raw.charAt(index)) < 0) index++;
                                    }
                                }
                                default -> {
                                }
                            }
                        }
                    }
                } else if (current == '\r' || current == '\n') {
                    index++;
                } else {
                    if (!skip) output.append(current);
                    index++;
                }
            }
            return output.toString();
        }

        private static Charset detectCharset(Path file) throws IOException {
            byte[] sample;
            try (InputStream input = Files.newInputStream(file)) {
                sample = input.readNBytes(64 * 1024);
            }
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

        private static String extension(Path file) {
            String name = file.getFileName().toString();
            int dot = name.lastIndexOf('.');
            return dot < 0 ? "" : name.substring(dot + 1).toLowerCase(Locale.ROOT);
        }

        private static void checkCancelled(BooleanSupplier cancelled) {
            if (cancelled.getAsBoolean() || Thread.currentThread().isInterrupted()) throw new CancellationException();
        }
    }

    private static final class MultiMatcher {
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

        private boolean feed(String value) {
            if (targets.isEmpty()) return false;
            for (int index = 0; index < targets.size(); index++) {
                if (found[index]) continue;
                String combined = tails[index] + value;
                if (normalize(combined).contains(targets.get(index))) {
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
}
