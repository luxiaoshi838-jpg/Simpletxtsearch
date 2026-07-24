package com.luxiaoshi.simpletxtsearch

import android.app.Application
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader

class SimpleSearchApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        PDFBoxResourceLoader.init(this)
    }
}
