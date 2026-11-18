import { useState } from "react";
import { FlatList, KeyboardAvoidingView, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

const categories = [
  { category_id: 1, category_name: "Hardware", category_desc: "Hardware issues" },
  { category_id: 2, category_name: "Software", category_desc: "Software issues" },
  { category_id: 3, category_name: "Cyber Incident", category_desc: "Security Issues" },
];

const tickets = [
  {
    ticket_id: 1,
    title: "Printer won't print",
    category_id: 1,
    priority: "Medium",
    status: "Open",
    assigned_to: "Unassigned",
    created_by: "John Doe",
    created: "October 20th 11:12am",
    ticket_desc: "My printer will not print, others are not having this issue and I also cannot send a test page.",
    comments: [
      {comment_id: 1, user: "John Doe", comment_desc: "I tried restarting the printer and it didn't help.", date_created: "November 1st 2:15pm"}
    ]
  },
  {
    ticket_id: 2,
    title: "External Email",
    category_id: 3,
    priority: "Low",
    status: "Open",
    assigned_to: "Unassigned",
    created_by: "CEO",
    created: "October 20th 12:12am",
    ticket_desc: "I clicked on a link in an email earlier today and now my computer is locked and asking for money what is happening.",

  },
  {
    ticket_id: 3,
    title: "Computer won't turn on",
    category_id: 1,
    priority: "High",
    status: "Open",
    assigned_to: "Andrew Greaves",
    created_by: "John Doe Jr",
    created: "October 22th 1:12pm",
    ticket_desc: "My computer will not turn on, the on light is white but nothing is on the screen",
  },
];



function DetailRow({ label, value }) {
  return (
    <View style={styles.row}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value}</Text>
    </View>
  );
}

function PriorityBadge({ label, color }) {
  return (
    <View
      style={{
        backgroundColor: color + "22",
        paddingHorizontal: 10,
        paddingVertical: 4,
        borderRadius: 999,
        alignSelf: "flex-start",
        marginTop: 6,
      }}
    >
     <Text style={{ color, fontSize: 12, fontWeight: "700" }}>{label}</Text> 
    </View>
  );
}

const priorityRank = {
  High: 1,
  Medium: 2,
  Low: 3,
};

const statusRank = {
  Open: 1,
  Closed: 2,
};

const priorityColors = {
  High: "#dc2626",
  Medium: "#f59e0b",
  Low: "#16a34a",
};

const theme = {
  colors: {},
};

const testUser = { email: "andrew@test.com", password: "password123"}


export default function App() {
  const [selectedQueue, setSelectedQueue] = useState(null);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [searchText, setSearchText] = useState("");
  const [sortBy, setSortBy] = useState("priority");
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState(false);
  const [replyText, setReplyText] = useState("");

  const sendReply = () => {
    if (replyText.trim() === "") return;

    const newComment = {
      comment_id: Date.now(),
      user: "Andrew Greaves",
      comment_desc: replyText,
      date_created: "Just Now",
    };

    selectedTicket.comments = [...(selectedTicket.comments ?? []), newComment];
    setReplyText("");
  };

  if(!isLoggedIn){
    return (
      <View style={styles.container}>
        <Text style={styles.header}>Sign In</Text>
        <TextInput
          style={styles.search}
          placeholder="Email"
          placeholderTextColor="#9ca3af"
          autoCapitalize="none"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          style={styles.search}
          placeholder="Password"
          placeholderTextColor="#9ca3af"
          secureTextEntry
          value={password}
          onChangeText={setPassword}
        />

        <Pressable
          style={styles.card}
          onPress={() => {
            if (email === testUser.email && password === testUser.password) {
              setIsLoggedIn(true);
            } else {
              setLoginError(true);
            }
          }}
        >
          <Text style={styles.cardTitle}>Continue</Text>
        </Pressable>
        {loginError && (
          <Text style={styles.errorText}>Email or password is incorrect please try again</Text>
        )}
      </View>
    );
  }

  if (selectedTicket) {
    return (
    <KeyboardAvoidingView style={styles.container} behavior="padding">
      <ScrollView keyboardShouldPersistTaps="handled">
        <Pressable onPress={() => setSelectedTicket(null)}>
          <Text style={styles.back}>← Back</Text>
        </Pressable>
        <Text style={styles.detailTitle}>{selectedTicket.title}</Text>

        <View style={styles.card}>
          <DetailRow label="Priority" value={selectedTicket.priority} />
          <DetailRow label="Status" value={selectedTicket.status} />
          <DetailRow label="Assigned to" value={selectedTicket.assigned_to ?? "Unassigned"} />
          <DetailRow label="Created by" value={selectedTicket.created_by} />
          <DetailRow label="Created" value={selectedTicket.created} />
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionLabel}>Description</Text>
          <Text style={styles.cardDesc}>{selectedTicket.ticket_desc}</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionLabel}>Comments</Text>
          {(selectedTicket.comments ?? []).map((c) => (
            <View key={c.comment_id} style={styles.commentRow}>
              <Text style={styles.commentUser}>{c.user} · {c.date_created} </Text>
              <Text style={styles.cardDesc}>{c.comment_desc}</Text>
            </View>
          ))}

          <TextInput
            style={styles.search}
            placeholder="Reply..."
            placeholderTextColor="#9ca3af"
            value={replyText}
            onChangeText={setReplyText}
            multiline
            />
            <Pressable style={styles.sendButton} onPress={sendReply}>
              <Text style={styles.sendText}>Send</Text>
            </Pressable>
        </View>

      </ScrollView>
    </KeyboardAvoidingView>
    );
  }

  if (selectedQueue) {
    const queueTickets = tickets.filter(
      (t) => t.category_id === selectedQueue.category_id && t.title.toLowerCase().includes(searchText.toLowerCase())
    );

    if (sortBy === "priority") {
      queueTickets.sort((a,b) => priorityRank[a.priority] - priorityRank[b.priority]);
    } else {
      queueTickets.sort((a, b) => statusRank[a.status] - statusRank[b.status]);
    }

    return (
      <View style={styles.container}>
        <Pressable onPress={() => setSelectedQueue(null)}>
          <Text style={styles.back}>← Back</Text>
        </Pressable>

        <Text style={styles.header}>{selectedQueue.category_name}</Text>
        <TextInput
          style={styles.search}
          placeholder="Search tickets..."
          placeholderTextColor="#9ca3af"
          value={searchText}
          onChangeText={setSearchText}
        />

        <FlatList
          data={queueTickets}
          keyExtractor={(item) => String(item.ticket_id)}
          ListEmptyComponent={<Text style={styles.cardDesc}>No tickets in this queue.</Text>}
          renderItem={({ item }) => (
            <Pressable style={styles.card} onPress={() => setSelectedTicket(item)}>
              <Text style={styles.cardTitle}>{item.title}</Text>
              <PriorityBadge label={item.priority} color={priorityColors[item.priority]} />
              <Text style={styles.cardDesc}>{item.status}</Text>
            </Pressable>
          )}
        />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Ticket Queues</Text>
      <FlatList
        data={categories}
        keyExtractor={(item) => String(item.category_id)}
        renderItem={({ item }) => (
          <Pressable style={styles.card} onPress={() => setSelectedQueue(item)}>
            <Text style={styles.cardTitle}>{item.category_name}</Text>
            <Text style={styles.cardDesc}>{item.category_desc}</Text>
            <Text style={styles.count}>
              {tickets.filter((t) => t.category_id === item.category_id).length} tickets
            </Text>
          </Pressable>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f172a", paddingTop: 60, paddingHorizontal: 16 },
  header: { fontSize: 28, fontWeight: "bold", marginBottom: 16, textAlign: "center", color: "#f1f5f9" },
  detailTitle: { fontSize: 24, fontWeight: "bold", color: "#f1f5f9", marginBottom: 16},
  back: { fontSize: 16, color: "#3b82f6", marginBottom: 12 },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: "#334155" },
  detailLabel: { fontSize: 14, color: "#94a3b8" },
  detailValue: { fontSize: 14, fontWeight: "600", color: "#f1f5f9" },
  sectionLabel: { fontSize: 12, color: "#94a3b8", marginBottom: 6 },
  search: {backgroundColor: "#1e293b", padding: 16, borderRadius: 15, fontSize: 16, marginBottom: 14, borderWidth: 0.75, borderColor: "#000", color: "#f1f5f9"},
  card: {
    backgroundColor: "#1e293b",
    padding: 18,
    borderRadius: 10,
    borderLeftWidth: 8,
    borderLeftColor: "#3b82f6",
    marginBottom: 14,
    shadowColor: "#000",
    shadowOpacity: 0.1,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  cardTitle: { fontSize: 18, fontWeight: "600", color: "#f1f5f9" },
  cardDesc: { fontSize: 14, color: "#f1f5f9", marginTop: 4 },
  count: { fontSize: 14, fontStyle: "italic", color: "#f1f5f9", marginTop: 4},
  priority: { fontSize: 14, fontWeight: "700"},
  errorText: { fontSize: 14, color: "#dc2626", marginTop: 12, textAlign: "center"},
  commentRow: {paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: "#334155"},
  commentUser: {fontSize: 12, fontWeight: "600", color: "#94a3b8", marginBottom: 2}, 
  sendButton: { backgroundColor: "#3b82f6", paddingVertical: 10, borderRadius: 10, alignItems: "center", marginTop: 8},
  sendText: { color: "white", fontWeight: "600", fontSize: 14},
});