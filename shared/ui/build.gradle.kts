plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.android.kotlin.multiplatform.library)
    alias(libs.plugins.compose.multiplatform)
    alias(libs.plugins.compose.compiler)
}

kotlin {
    android {
        namespace = "dev.hermeskotlin.ui"
        compileSdk = libs.versions.android.compileSdk.get().toInt()
        minSdk = libs.versions.android.minSdk.get().toInt()
        // The RTL layout harness renders the real components under Robolectric, so the host test needs the
        // module's merged Android resources (the app's fonts and theme) rather than stubs.
        withHostTest { isIncludeAndroidResources = true }
    }

    sourceSets {
        commonMain.dependencies {
            api(projects.shared.core)
            api(projects.shared.designsystem)
            implementation(libs.lifecycle.viewmodel.compose)
            implementation(libs.lifecycle.runtime.compose)
            implementation(libs.koin.core)
            implementation(libs.koin.compose.viewmodel)
            implementation(libs.compose.ui.tooling.preview)
            implementation(libs.haze)
            implementation(libs.haze.blur)
        }
        androidMain.dependencies {
            implementation(libs.androidx.activity.compose)
            implementation(libs.androidx.core.ktx)
            // The Health switch asks for Health Connect's permissions through its own screen.
            implementation(libs.androidx.health.connect)
        }
        commonTest.dependencies {
            implementation(libs.kotlin.test)
            implementation(libs.kotlinx.coroutines.test)
            implementation(libs.ktor.client.mock)
        }
        // Rendered RTL layout tests: Robolectric hosts the real Compose measurement and pixels.
        getByName("androidHostTest").dependencies {
            implementation(libs.junit4)
            implementation(libs.robolectric)
            implementation(libs.compose.ui.test.junit4)
        }
    }
}

// Lint only ever gets this module's test sources, and the app's lint ignores those (see androidApp).
tasks.matching { it.name == "lintAnalyzeAndroidHostTest" }.configureEach { enabled = false }
