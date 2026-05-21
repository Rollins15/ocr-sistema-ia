// App.jsx — ponto de entrada React Native
// Instalar dependências:
//   npx expo install expo-image-picker
//   npm install @react-navigation/native @react-navigation/stack
//   npx expo install react-native-screens react-native-safe-area-context

import { NavigationContainer } from "@react-navigation/native";
import { createStackNavigator } from "@react-navigation/stack";
import HomeScreen from "./src/screens/HomeScreen";

const Stack = createStackNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: "#1a56db" },
          headerTintColor: "white",
          headerTitleStyle: { fontWeight: "700" },
        }}
      >
        <Stack.Screen
          name="Home"
          component={HomeScreen}
          options={{ title: "OCR · Leitura de Texto" }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
