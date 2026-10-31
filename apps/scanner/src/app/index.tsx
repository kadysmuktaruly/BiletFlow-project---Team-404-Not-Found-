import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { useAuth } from "@/lib/auth";

export default function Index() {
  const { status } = useAuth();
  if (status === "loading") {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator size="large" />
      </View>
    );
  }
  return <Redirect href={status === "authenticated" ? "/home" : "/login"} />;
}
