package com.truthlens.mobile.data

class TruthLensRepository {
    fun api(settings: AppSettings): TruthLensApi {
        return TruthLensApiFactory.create(settings.apiBaseUrl, settings.apiKey)
    }
}
