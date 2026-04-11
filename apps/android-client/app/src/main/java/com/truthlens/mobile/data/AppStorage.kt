package com.truthlens.mobile.data

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.truthlens.mobile.BuildConfig
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.truthLensDataStore by preferencesDataStore(name = "truthlens_mobile")

class SettingsStore(
    private val context: Context,
    private val gson: Gson = Gson(),
) {
    private object Keys {
        val ApiBaseUrl = stringPreferencesKey("api_base_url")
        val ApiKey = stringPreferencesKey("api_key")
        val AutoOptimize = booleanPreferencesKey("auto_optimize")
        val ShowDebug = booleanPreferencesKey("show_debug")
        val Recents = stringPreferencesKey("recent_analyses_json")
    }

    val settingsFlow: Flow<AppSettings> = context.truthLensDataStore.data.map { preferences ->
        AppSettings(
            apiBaseUrl = preferences[Keys.ApiBaseUrl] ?: BuildConfig.TRUTHLENS_DEFAULT_API_BASE,
            apiKey = preferences[Keys.ApiKey] ?: "",
            autoOptimizeDrafts = preferences[Keys.AutoOptimize] ?: true,
            showDebugInfo = preferences[Keys.ShowDebug] ?: false,
        )
    }

    val recentAnalysesFlow: Flow<List<RecentAnalysisEntry>> = context.truthLensDataStore.data.map { preferences ->
        decodeRecents(preferences)
    }

    suspend fun saveSettings(settings: AppSettings) {
        context.truthLensDataStore.edit { preferences ->
            preferences[Keys.ApiBaseUrl] = settings.apiBaseUrl
            preferences[Keys.ApiKey] = settings.apiKey
            preferences[Keys.AutoOptimize] = settings.autoOptimizeDrafts
            preferences[Keys.ShowDebug] = settings.showDebugInfo
        }
    }

    suspend fun prependRecent(entry: RecentAnalysisEntry) {
        context.truthLensDataStore.edit { preferences ->
            val updated = buildList {
                add(entry)
                addAll(decodeRecents(preferences).filterNot { it.targetUrl == entry.targetUrl }.take(11))
            }
            preferences[Keys.Recents] = gson.toJson(updated)
        }
    }

    private fun decodeRecents(preferences: Preferences): List<RecentAnalysisEntry> {
        val raw = preferences[Keys.Recents].orEmpty()
        if (raw.isBlank()) {
            return emptyList()
        }
        return runCatching {
            gson.fromJson<List<RecentAnalysisEntry>>(
                raw,
                object : TypeToken<List<RecentAnalysisEntry>>() {}.type,
            )
        }.getOrDefault(emptyList())
    }
}
