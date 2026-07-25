package com.luxiaoshi.simpletxtsearch.pc;

import javax.swing.BorderFactory;
import javax.swing.JList;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.ListCellRenderer;
import javax.swing.SwingUtilities;
import javax.swing.UIManager;
import java.awt.Color;
import java.awt.Component;
import java.awt.Dimension;
import java.awt.Font;
import java.awt.Graphics;
import java.awt.Window;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Path;

public final class SimpleTxtSearchPcLauncher {
    private static final double NAME_COLUMN_RATIO = 0.32;

    private SimpleTxtSearchPcLauncher() {
    }

    public static void main(String[] args) {
        SimpleTxtSearchPc.main(args);
        SwingUtilities.invokeLater(SimpleTxtSearchPcLauncher::installTwoColumnResults);
    }

    private static void installTwoColumnResults() {
        for (Window window : Window.getWindows()) {
            if (!(window instanceof SimpleTxtSearchPc frame)) continue;
            try {
                Field resultListField = SimpleTxtSearchPc.class.getDeclaredField("resultList");
                resultListField.setAccessible(true);
                Object value = resultListField.get(frame);
                if (value instanceof JList<?> resultList) {
                    configureResultList(resultList);
                }
            } catch (ReflectiveOperationException error) {
                throw new IllegalStateException("无法初始化搜索结果两列布局", error);
            }
        }
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    private static void configureResultList(JList<?> resultList) {
        ((JList) resultList).setCellRenderer(new ResultRenderer());
        resultList.setFixedCellHeight(32);

        Component ancestor = SwingUtilities.getAncestorOfClass(JScrollPane.class, resultList);
        if (ancestor instanceof JScrollPane scrollPane) {
            scrollPane.setColumnHeaderView(new ResultHeader());
        }
    }

    private static Path extractPath(Object value) {
        if (value == null) return null;
        try {
            Method pathMethod = value.getClass().getDeclaredMethod("path");
            pathMethod.setAccessible(true);
            Object result = pathMethod.invoke(value);
            return result instanceof Path path ? path : null;
        } catch (ReflectiveOperationException ignored) {
            return null;
        }
    }

    private static final class ResultRenderer extends TwoColumnPanel implements ListCellRenderer<Object> {
        private ResultRenderer() {
            super(false);
        }

        @Override
        public Component getListCellRendererComponent(
            JList<?> list,
            Object value,
            int index,
            boolean isSelected,
            boolean cellHasFocus
        ) {
            Path path = extractPath(value);
            String name = path == null || path.getFileName() == null ? String.valueOf(value) : path.getFileName().toString();
            Path parent = path == null ? null : path.getParent();
            String location = parent == null ? "" : parent.toString();

            setValues(name, location);
            setToolTips(name, location);
            setFont(list.getFont());
            setColors(
                isSelected ? list.getSelectionBackground() : list.getBackground(),
                isSelected ? list.getSelectionForeground() : list.getForeground()
            );
            setBorder(cellHasFocus
                ? UIManager.getBorder("List.focusCellHighlightBorder")
                : BorderFactory.createEmptyBorder(0, 0, 1, 0));
            return this;
        }
    }

    private static final class ResultHeader extends TwoColumnPanel {
        private ResultHeader() {
            super(true);
            setValues("名称", "文件位置");
            Font baseFont = UIManager.getFont("TableHeader.font");
            if (baseFont != null) setFont(baseFont.deriveFont(Font.BOLD));
            Color background = UIManager.getColor("TableHeader.background");
            Color foreground = UIManager.getColor("TableHeader.foreground");
            setColors(background == null ? UIManager.getColor("Panel.background") : background,
                foreground == null ? UIManager.getColor("Label.foreground") : foreground);
            setBorder(BorderFactory.createCompoundBorder(
                UIManager.getBorder("TableHeader.cellBorder"),
                BorderFactory.createEmptyBorder(0, 0, 0, 0)
            ));
            setPreferredSize(new Dimension(0, 32));
        }
    }

    private static class TwoColumnPanel extends JPanel {
        private static final int HORIZONTAL_PADDING = 10;
        private final JLabel nameLabel = new JLabel();
        private final JLabel locationLabel = new JLabel();
        private final boolean header;
        private int dividerX;

        private TwoColumnPanel(boolean header) {
            this.header = header;
            setLayout(null);
            setOpaque(true);
            nameLabel.setOpaque(false);
            locationLabel.setOpaque(false);
            add(nameLabel);
            add(locationLabel);
        }

        protected final void setValues(String name, String location) {
            nameLabel.setText(name);
            locationLabel.setText(location);
        }

        protected final void setToolTips(String name, String location) {
            nameLabel.setToolTipText(name);
            locationLabel.setToolTipText(location);
        }

        protected final void setColors(Color background, Color foreground) {
            setBackground(background);
            nameLabel.setForeground(foreground);
            locationLabel.setForeground(foreground);
        }

        @Override
        public void setFont(Font font) {
            super.setFont(font);
            if (nameLabel != null) nameLabel.setFont(font);
            if (locationLabel != null) locationLabel.setFont(font);
        }

        @Override
        public void doLayout() {
            int width = getWidth();
            int height = getHeight();
            dividerX = Math.max(220, (int) Math.round(width * NAME_COLUMN_RATIO));
            dividerX = Math.min(dividerX, Math.max(220, width - 260));
            nameLabel.setBounds(HORIZONTAL_PADDING, 0, Math.max(0, dividerX - HORIZONTAL_PADDING * 2), height);
            locationLabel.setBounds(dividerX + HORIZONTAL_PADDING, 0,
                Math.max(0, width - dividerX - HORIZONTAL_PADDING * 2), height);
        }

        @Override
        protected void paintComponent(Graphics graphics) {
            super.paintComponent(graphics);
            Color divider = UIManager.getColor(header ? "TableHeader.foreground" : "Separator.foreground");
            if (divider == null) divider = getForeground();
            graphics.setColor(divider);
            graphics.drawLine(dividerX, 0, dividerX, getHeight());
            if (!header) graphics.drawLine(0, getHeight() - 1, getWidth(), getHeight() - 1);
        }
    }
}
