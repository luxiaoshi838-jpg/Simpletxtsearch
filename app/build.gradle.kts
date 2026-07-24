plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val releaseStorePath = System.getenv("SIMPLETXTSEARCH_KEYSTORE_PATH")
val releaseStorePassword = System.getenv("SIMPLETXTSEARCH_KEYSTORE_PASSWORD")
val releaseKeyAlias = System.getenv("SIMPLETXTSEARCH_KEY_ALIAS")
val releaseKeyPassword = System.getenv("SIMPLETXTSEARCH_KEY_PASSWORD")
val releaseSigningConfigured = listOf(
    releaseStorePath,
    releaseStorePassword,
    releaseKeyAlias,
    releaseKeyPassword
).all { !it.isNullOrBlank() }

android {
    namespace = "com.luxiaoshi.simpletxtsearch"
    compileSdk = 35

    val generatedVersionCode = (System.getenv("SIMPLETXTSEARCH_VERSION_CODE") ?: "2026072401")
        .toIntOrNull() ?: 2026072401
    val generatedVersionName = System.getenv("SIMPLETXTSEARCH_VERSION_NAME") ?: "1.0.0"

    defaultConfig {
        applicationId = "com.luxiaoshi.simpletxtsearch"
        minSdk = 26
        targetSdk = 35
        versionCode = generatedVersionCode
        versionName = generatedVersionName
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        if (releaseSigningConfigured) {
            create("stableRelease") {
                storeFile = file(requireNotNull(releaseStorePath))
                storePassword = requireNotNull(releaseStorePassword)
                keyAlias = requireNotNull(releaseKeyAlias)
                keyPassword = requireNotNull(releaseKeyPassword)
                enableV1Signing = true
                enableV2Signing = true
            }
        }
    }

    buildTypes {
        release {
            if (releaseSigningConfigured) {
                signingConfig = signingConfigs.getByName("stableRelease")
            }
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
    }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("androidx.activity:activity-ktx:1.9.0")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.documentfile:documentfile:1.0.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("com.github.albfernandez:juniversalchardet:2.5.0")

    testImplementation("junit:junit:4.13.2")
}
