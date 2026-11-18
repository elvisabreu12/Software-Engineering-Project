import { View, Text, FlatList, StyleSheet } from "react-native";

const categories = [
  { category_id: 1, category_name: "Hardware", category_desc: "Hardware issues" },
  { category_id: 2, category_name: "Software", category_desc: "Software issues" },
];

export default function App() {
  return (
    <View style={styles.container}>
      <Text style={styles.header}>Ticket Queues</Text>
      <FlatList
        data={categories}
        keyExtractor={(item) => String(item.category_id)}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>{item.category_name}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, paddingTop: 60, paddingHorizontal: 16 },
  header: { fontSize: 28, fontWeight: "bold", marginBottom: 16 },
  card: { backgroundColor: "white", padding: 16, borderRadius: 10, marginBottom: 12 },
  cardTitle: { fontSize: 18, fontWeight: "600" },
});
