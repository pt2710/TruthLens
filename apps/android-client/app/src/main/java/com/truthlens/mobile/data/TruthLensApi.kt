package com.truthlens.mobile.data

import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.POST

interface TruthLensApi {
    @POST("mobile/analyze-share")
    suspend fun analyzeShare(@Body request: MobileAnalyzeShareRequestDto): MobileAnalyzeShareResponseDto

    @POST("manual-report/optimize")
    suspend fun optimizeReport(@Body request: ManualReportOptimizationRequestDto): ManualReportOptimizationResponseDto

    @POST("feedback")
    suspend fun submitFeedback(@Body request: FeedbackEventDto)

    @POST("youtube/report")
    suspend fun submitYouTubeReport(@Body request: YouTubeReportRequestDto): YouTubeReportResponseDto
}

object TruthLensApiFactory {
    fun create(baseUrl: String, apiKey: String): TruthLensApi {
        val normalizedBaseUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }
        val apiKeyInterceptor = Interceptor { chain ->
            val requestBuilder = chain.request().newBuilder()
            if (apiKey.isNotBlank()) {
                requestBuilder.addHeader("x-truthlens-api-key", apiKey)
            }
            chain.proceed(requestBuilder.build())
        }
        val client = OkHttpClient.Builder()
            .addInterceptor(apiKeyInterceptor)
            .addInterceptor(logging)
            .build()

        return Retrofit.Builder()
            .baseUrl(normalizedBaseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(TruthLensApi::class.java)
    }
}
