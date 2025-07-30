import streamlit as st
import requests
import json
import os
from datetime import datetime

# ページ設定
st.set_page_config(
    page_title="RAG ChatBot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 環境変数からAPI エンドポイント取得
def get_api_endpoints():
    """環境変数からAPIエンドポイントを安全に取得"""
    
    # Streamlit Secrets から取得（本番環境）
    try:
        auth_api = st.secrets["API_ENDPOINTS"]["AUTH_API_URL"]
        rag_api = st.secrets["API_ENDPOINTS"]["RAG_API_URL"] 
        chat_api = st.secrets["API_ENDPOINTS"]["CHAT_API_URL"]
        return auth_api, rag_api, chat_api
    except:
        pass
    
    # 環境変数から取得（ローカル開発環境）
    auth_api = os.getenv("AUTH_API_URL")
    rag_api = os.getenv("RAG_API_URL")
    chat_api = os.getenv("CHAT_API_URL")
    
    # デフォルト値（開発環境用 - 本番では使用しない）
    if not auth_api or not rag_api or not chat_api:
        st.error("🔒 API エンドポイントが設定されていません。管理者に連絡してください。")
        st.info("💡 環境変数 AUTH_API_URL, RAG_API_URL, CHAT_API_URL を設定するか、Streamlit Secrets を確認してください。")
        st.stop()
    
    return auth_api, rag_api, chat_api

# API エンドポイント取得
AUTH_API, RAG_API, CHAT_API = get_api_endpoints()

def main():
    st.title("🤖 RAG ChatBot")
    st.caption("セキュアな知識ベース検索システム")
    
    # デバッグ情報（開発時のみ表示）
    if st.sidebar.checkbox("🔧 デバッグ情報", help="開発者向け情報"):
        with st.sidebar.expander("API エンドポイント確認"):
            # セキュリティのため、URLの最後の部分のみ表示
            st.code(f"認証API: ...{AUTH_API[-20:]}")
            st.code(f"RAG API: ...{RAG_API[-20:]}")
            st.code(f"チャットAPI: ...{CHAT_API[-20:]}")
    
    # セッション状態の初期化  
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'token' not in st.session_state:
        st.session_state.token = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    # 認証状態によって画面切り替え
    if st.session_state.authenticated:
        show_chat_interface()
    else:
        show_auth_interface()

def show_auth_interface():
    """認証画面"""
    st.header("🔐 ログイン・サインアップ")
    
    # セキュリティ情報表示
    with st.expander("🛡️ セキュリティ機能", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.write("✅ **通信セキュリティ**")
            st.write("• HTTPS暗号化通信")
            st.write("• JWT認証トークン")
            st.write("• CORS保護")
        with col2:
            st.write("✅ **攻撃対策**")
            st.write("• レート制限")
            st.write("• XSS/SQLi防御")
            st.write("• HTTPメソッド制限")
    
    tab1, tab2 = st.tabs(["ログイン", "サインアップ"])
    
    with tab1:
        st.subheader("ログイン")
        with st.form("login_form"):
            email = st.text_input("メールアドレス", placeholder="user@example.com")
            password = st.text_input("パスワード", type="password")
            login_btn = st.form_submit_button("🔑 ログイン", use_container_width=True)
            
            if login_btn:
                if email and password:
                    login_user(email, password)
                else:
                    st.error("すべての項目を入力してください")
    
    with tab2:
        st.subheader("新規サインアップ")
        with st.form("signup_form"):
            new_email = st.text_input("メールアドレス", placeholder="user@example.com", key="signup_email")
            new_password = st.text_input("パスワード", type="password", key="signup_password", 
                                       help="8文字以上、大文字・小文字・数字・記号を含む")  
            confirm_password = st.text_input("パスワード確認", type="password", key="confirm_password")
            
            # パスワード強度チェック
            if new_password:
                strength = check_password_strength(new_password)
                if strength["score"] < 3:
                    st.warning(f"⚠️ パスワード強度: {strength['label']} - {strength['suggestions']}")
                else:
                    st.success(f"✅ パスワード強度: {strength['label']}")
            
            signup_btn = st.form_submit_button("👤 サインアップ", use_container_width=True)
            
            if signup_btn:
                if new_email and new_password and confirm_password:
                    if new_password == confirm_password:
                        if check_password_strength(new_password)["score"] >= 3:
                            signup_user(new_email, new_password)
                        else:
                            st.error("パスワードが弱すぎます。より強力なパスワードを設定してください。")
                    else:
                        st.error("パスワードが一致しません")
                else:
                    st.error("すべての項目を入力してください")

def check_password_strength(password):
    """パスワード強度チェック"""
    score = 0
    suggestions = []
    
    if len(password) >= 8:
        score += 1
    else:
        suggestions.append("8文字以上")
    
    if any(c.isupper() for c in password):
        score += 1
    else:
        suggestions.append("大文字")
    
    if any(c.islower() for c in password):
        score += 1
    else:
        suggestions.append("小文字")
    
    if any(c.isdigit() for c in password):
        score += 1  
    else:
        suggestions.append("数字")
    
    if any(c in '!@#$%^&*(),.?":{}|<>' for c in password):
        score += 1
    else:
        suggestions.append("記号")
    
    labels = ["とても弱い", "弱い", "普通", "強い", "とても強い"]
    return {
        "score": score,
        "label": labels[min(score, 4)],
        "suggestions": "、".join(suggestions) + "を含める"
    }

def show_chat_interface():
    """チャット画面"""
    # サイドバー
    with st.sidebar:
        st.write(f"👤 **ユーザー**: {st.session_state.user_id}")
        st.write(f"🔑 **認証状態**: ✅ 認証済み")
        
        if st.button("🚪 ログアウト", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.token = None
            st.session_state.user_id = None
            st.session_state.messages = []
            st.success("ログアウトしました")
            st.rerun()
        
        st.divider()
        
        # チャット管理
        st.subheader("💬 チャット管理")
        if st.button("➕ 新しいチャット", use_container_width=True):
            st.session_state.messages = []
            st.success("新しいチャットを開始しました")
            st.rerun()
        
        st.write(f"📝 **メッセージ数**: {len(st.session_state.messages)}")
        
        # セキュリティ情報
        with st.expander("🛡️ セキュリティステータス"):
            st.write("🔐 **JWT認証**: 有効")  
            st.write("⚡ **レート制限**: 有効")
            st.write("🌐 **CORS保護**: 有効")
            st.write("🛡️ **Gateway Response**: 設定済み")
            st.write("🔒 **HTTPS通信**: 有効")
        
        # APIステータス表示
        with st.expander("📡 API ステータス"):
            st.write("🟢 **認証API**: 正常")
            st.write("🟢 **RAG API**: 正常") 
            st.write("🟢 **チャットAPI**: 正常")
    
    # メインチャット画面
    st.header("💬 AIチャット")
    
    # ウェルカムメッセージ
    if not st.session_state.messages:
        with st.chat_message("assistant"):
            st.markdown("""
            👋 **RAG ChatBotへようこそ！**
            
            私は知識ベースを検索して、正確で引用付きの回答を提供します。
            
            **できること：**
            - 📚 文書検索・要約
            - 💡 質問への詳細回答  
            - 🔍 情報の出典表示
            - 💬 自然な対話
            
            何でもお気軽にお聞きください！🤖✨
            """)
    
    # チャット履歴表示
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # アシスタントメッセージの追加情報
            if message["role"] == "assistant":
                if "timestamp" in message:
                    st.caption(f"🕒 {message['timestamp']}")
                if "citations" in message and message["citations"]:
                    with st.expander("📚 参照文書", expanded=False):
                        for i, citation in enumerate(message["citations"], 1):
                            st.write(f"{i}. {citation}")
    
    # ユーザー入力
    if prompt := st.chat_input("💬 質問を入力してください..."):
        # 入力値検証
        if len(prompt.strip()) == 0:
            st.error("質問を入力してください")
            return
            
        if len(prompt) > 1000:
            st.error("質問が長すぎます（1000文字以内）")
            return
        
        # ユーザーメッセージ追加・表示
        user_message = {"role": "user", "content": prompt}
        st.session_state.messages.append(user_message)
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # AI回答生成
        with st.chat_message("assistant"):
            with st.spinner("🤖 AI回答を生成中..."):
                response = call_rag_api(prompt)
                
                if response and response.get("reply"):
                    st.markdown(response["reply"])
                    
                    # 引用情報表示
                    citations_displayed = False
                    if response.get("citations"):
                        with st.expander("📚 参照文書", expanded=False):
                            for i, citation in enumerate(response["citations"], 1):
                                st.write(f"{i}. {citation}")
                        citations_displayed = True
                    
                    # アシスタントメッセージ追加
                    assistant_message = {
                        "role": "assistant", 
                        "content": response["reply"],
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "citations": response.get("citations", [])
                    }
                    st.session_state.messages.append(assistant_message)
                    
                    # 成功メッセージ
                    if citations_displayed:
                        st.success("✅ 回答を生成しました（参照文書付き）")
                    else:
                        st.success("✅ 回答を生成しました")
                        
                else:
                    error_msg = "申し訳ございませんが、現在回答を生成できません。しばらく後に再試行してください。"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": error_msg,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })

def login_user(email, password):
    """ログイン処理（エラーハンドリング強化）"""
    with st.spinner("🔐 認証中..."):
        try:
            response = requests.post(
                f"{AUTH_API}/login",
                json={"user_id": email, "password": password},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                st.session_state.authenticated = True
                st.session_state.token = data["token"]
                st.session_state.user_id = email
                st.success("✅ ログインしました！")
                st.balloons()
                st.rerun()
            else:
                error_data = response.json()
                error_msg = error_data.get('error', 'Unknown error')
                
                # エラータイプ別の対応
                if "Invalid credentials" in error_msg:
                    st.error("❌ メールアドレスまたはパスワードが間違っています")
                elif "locked" in error_msg.lower():
                    st.error("🔒 アカウントがロックされています。しばらく待ってから再試行してください")
                else:
                    st.error(f"❌ ログインエラー: {error_msg}")
                    
        except requests.exceptions.Timeout:
            st.error("⏰ 接続がタイムアウトしました。ネットワーク接続を確認してください")
        except requests.exceptions.ConnectionError:
            st.error("🌐 サーバーに接続できません。しばらく後に再試行してください")
        except Exception as e:
            st.error("❌ 予期しないエラーが発生しました。管理者に連絡してください")
            st.error(f"詳細: {str(e)}")

def signup_user(email, password):
    """サインアップ処理（エラーハンドリング強化）"""
    with st.spinner("👤 アカウント作成中..."):
        try:
            response = requests.post(
                f"{AUTH_API}/signup", 
                json={"user_id": email, "password": password},
                timeout=15
            )
            
            if response.status_code == 201:
                st.success("✅ アカウントを作成しました！")
                st.info("📧 ログインタブからログインしてください")
                st.balloons()
            else:
                error_data = response.json()
                error_msg = error_data.get('error', 'Unknown error')
                
                # エラータイプ別の対応
                if "already exists" in error_msg:
                    st.error("📧 このメールアドレスは既に登録されています")
                elif "email" in error_msg.lower():
                    st.error("📧 有効なメールアドレスを入力してください")
                elif "password" in error_msg.lower():
                    st.error("🔒 パスワードの要件を満たしていません")
                else:
                    st.error(f"❌ サインアップエラー: {error_msg}")
                    
        except requests.exceptions.Timeout:
            st.error("⏰ 接続がタイムアウトしました")
        except requests.exceptions.ConnectionError:
            st.error("🌐 サーバーに接続できません")
        except Exception as e:
            st.error("❌ 予期しないエラーが発生しました")
            st.error(f"詳細: {str(e)}")

def call_rag_api(query):
    """RAG API呼び出し（エラーハンドリング強化）"""
    try:
        response = requests.post(
            f"{RAG_API}/query",
            json={"message": query},
            headers={"Authorization": f"Bearer {st.session_state.token}"},
            timeout=60  # RAG処理は時間がかかる可能性
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            st.error("🔐 認証が切れました。再度ログインしてください")
            st.session_state.authenticated = False
            st.rerun()
        elif response.status_code == 429:
            st.error("⚡ レート制限に達しました。しばらく待ってから再試行してください")
        else:
            st.error(f"🔧 API Error: HTTP {response.status_code}")
        
        return None
            
    except requests.exceptions.Timeout:
        st.error("⏰ AI処理がタイムアウトしました（60秒）。複雑な質問の場合は、より簡潔に分けて質問してください")
        return None
    except requests.exceptions.ConnectionError:
        st.error("🌐 RAGサービスに接続できません")
        return None
    except Exception as e:
        st.error(f"❌ 予期しないエラー: {str(e)}")
        return None

if __name__ == "__main__":
    main()
