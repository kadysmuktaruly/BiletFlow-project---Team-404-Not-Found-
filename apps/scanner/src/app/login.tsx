import { router } from "expo-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { KeyboardAvoidingView, Platform } from "react-native";

import { Banner, Body, Button, Field, Screen, Title } from "@/components/ui";
import { errorKey } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginScreen() {
  const { t, i18n } = useTranslation();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      router.replace("/home");
    } catch (err) {
      setError(t(errorKey(err, (k) => i18n.exists(k))));
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <Screen>
        <Title>{t("login.title")}</Title>
        <Body>{t("login.lead")}</Body>
        {error ? <Banner kind="error">{error}</Banner> : null}
        <Field
          label={t("login.email")}
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          textContentType="username"
        />
        <Field
          label={t("login.password")}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete="password"
          textContentType="password"
          onSubmitEditing={submit}
        />
        <Button title={t("login.submit")} onPress={submit} busy={busy} />
      </Screen>
    </KeyboardAvoidingView>
  );
}
