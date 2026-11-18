import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  type TextInputProps,
} from "react-native";

export const colors = {
  ink: "#111827",
  muted: "#4b5563",
  border: "#d1d5db",
  surface: "#ffffff",
  background: "#f3f4f6",
  danger: "#b91c1c",
  dangerBg: "#fef2f2",
  success: "#15803d",
  successBg: "#f0fdf4",
};

export function Screen({ children }: { children: React.ReactNode }) {
  return <View style={styles.screen}>{children}</View>;
}

export function Title({ children }: { children: React.ReactNode }) {
  return (
    <Text accessibilityRole="header" style={styles.title}>
      {children}
    </Text>
  );
}

export function Body({ children }: { children: React.ReactNode }) {
  return <Text style={styles.body}>{children}</Text>;
}

export function Field({ label, ...input }: TextInputProps & { label: string }) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={colors.muted}
        style={styles.input}
        {...input}
      />
    </View>
  );
}

export function Button({
  title,
  onPress,
  busy,
  variant = "primary",
}: {
  title: string;
  onPress: () => void;
  busy?: boolean;
  variant?: "primary" | "secondary";
}) {
  const primary = variant === "primary";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ busy: !!busy, disabled: !!busy }}
      disabled={busy}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        primary ? styles.buttonPrimary : styles.buttonSecondary,
        pressed && { opacity: 0.8 },
      ]}
    >
      {busy ? (
        <ActivityIndicator color={primary ? "#fff" : colors.ink} />
      ) : (
        <Text style={[styles.buttonText, { color: primary ? "#fff" : colors.ink }]}>{title}</Text>
      )}
    </Pressable>
  );
}

export function Banner({ kind, children }: { kind: "error" | "success"; children: string }) {
  const error = kind === "error";
  return (
    <View
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
      style={[styles.banner, { backgroundColor: error ? colors.dangerBg : colors.successBg }]}
    >
      <Text style={{ color: error ? colors.danger : colors.success, fontSize: 16 }}>{children}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background, padding: 24, gap: 16 },
  title: { fontSize: 26, fontWeight: "700", color: colors.ink },
  body: { fontSize: 16, lineHeight: 22, color: colors.muted },
  field: { gap: 6 },
  label: { fontSize: 15, fontWeight: "600", color: colors.ink },
  input: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 17,
    color: colors.ink,
  },
  button: { borderRadius: 8, paddingVertical: 14, alignItems: "center", minHeight: 48 },
  buttonPrimary: { backgroundColor: colors.ink },
  buttonSecondary: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  buttonText: { fontSize: 17, fontWeight: "600" },
  banner: { borderRadius: 8, padding: 14 },
});
