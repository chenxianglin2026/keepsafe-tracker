# Add project specific ProGuard rules here.
# By default, the flags in this file are appended to flags specified
# in the SDK tools.

# Keep Retrofit interfaces
-keep,allowobfuscation class com.keepsafe.app.data.model.** { *; }
-keep,allowobfuscation interface com.keepsafe.app.data.api.** { *; }
-keep,allowobfuscation class com.keepsafe.app.data.api.** { *; }

# Keep Gson serialized classes
-keepclassmembers class * {
    @com.google.gson.annotations.SerializedName <fields>;
}

# Keep data model classes
-keep class com.keepsafe.app.data.model.** { *; }
