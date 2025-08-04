import streamlit as st
import requests
import json
import html
import re
import os
import time
from datetime import datetime

# セキュリティ設定
st.set_page_config(
    page_title="RAG ChatBot",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 環境変数からAPI エンドポイント取得
def get_api_endpoints():
    """環境変数からAPIエンドポイントを安全に取得"""
    try:
        auth_api = st.secrets["API_ENDPOINTS"]["AUTH_API_URL"]
        rag_api = st.secrets["API_ENDPOINTS"]["RAG_API_URL"] 
        chat_api = st.secrets["API_ENDPOINTS"]["CHAT_API_URL"]
        # FILE_ACCESS_API_URL は必須ではないため、エラーを無視
        try:
            file_access_api = st.secrets["API_ENDPOINTS"]["FILE_ACCESS_API_URL"]
        except:
            file_access_api = None
        return auth_api, rag_api, chat_api, file_access_api
    except:
        pass
    
    auth_api = os.getenv("AUTH_API_URL")
    rag_api = os.getenv("RAG_API_URL")
    chat_api = os.getenv("CHAT_API_URL")
    file_access_api = os.getenv("FILE_ACCESS_API_URL")  # None でも許可
    
    if not auth_api or not rag_api or not chat_api:
        st.error("🔒 API エンドポイントが設定されていません。管理者に連絡してください。")
        st.info("💡 環境変数 AUTH_API_URL, RAG_API_URL, CHAT_API_URL を設定するか、Streamlit Secrets を確認してください。")
        st.stop()
    
    return auth_api, rag_api, chat_api, file_access_api

# API エンドポイント取得
AUTH_API, RAG_API, CHAT_API, FILE_ACCESS_API = get_api_endpoints()

def sanitize_input(text):
    """入力値のサニタイゼーション"""
    if not isinstance(text, str):
        return ""
    
    text = html.escape(text)
    if len(text) > 5000:
        text = text[:5000]
    
    dangerous_patterns = [
        r'<script.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe.*?</iframe>',
        r'<object.*?</object>',
        r'<embed.*?</embed>'
    ]
    
    for pattern in dangerous_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    return text.strip()

def verify_jwt_token(token):
    """JWTトークンの検証"""
    if not token:
        return None
    
    try:
        response = requests.get(
            f"{AUTH_API}/verify",
            headers={
                'Authorization': f'Bearer {token}',
                'User-Agent': 'RAG-ChatBot/1.0'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json().get('user_id')
        elif response.status_code == 401:
            error_data = response.json()
            if error_data.get('code') == 'TOKEN_EXPIRED':
                st.error("セッションが期限切れです。再度ログインしてください。")
            else:
                st.error("認証が無効です。再度ログインしてください。")
        return None
    except requests.exceptions.Timeout:
        st.error("認証サーバーへの接続がタイムアウトしました。")
        return None
    except Exception as e:
        st.error("認証エラーが発生しました。")
        return None

def load_chat_sessions(token):
    """チャットセッション一覧の取得"""
    try:
        response = requests.get(
            f"{CHAT_API}/sessions",
            headers={
                'Authorization': f'Bearer {token}',
                'User-Agent': 'RAG-ChatBot/1.0'
            },
            timeout=15
        )
        if response.status_code == 200:
            sessions = response.json().get('sessions', [])
            print(f"DEBUG: Loaded {len(sessions)} sessions")  # デバッグ出力
            return sessions
        else:
            print(f"DEBUG: Failed to load sessions, status: {response.status_code}")
        return []
    except requests.exceptions.Timeout:
        st.error("セッション一覧の取得がタイムアウトしました。")
        return []
    except Exception as e:
        print(f"DEBUG: Session load error: {str(e)}")
        return []

def delete_chat_session(session_id, token):
    """チャットセッションの削除"""
    try:
        response = requests.delete(
            f"{CHAT_API}/sessions/{session_id}",
            headers={
                'Authorization': f'Bearer {token}',
                'User-Agent': 'RAG-ChatBot/1.0'
            },
            timeout=10
        )
        return response.status_code == 200
    except:
        return False

def get_current_session_title(current_session_id, chat_sessions):
    """現在のセッションのタイトルを取得"""
    if not current_session_id:
        return "新規チャット"
    
    for session in chat_sessions:
        if session.get('session_id') == current_session_id:
            title = session.get('title', '無題のチャット')
            print(f"DEBUG: Found session title: {title}")  # デバッグ出力
            return title
    
    print(f"DEBUG: Session {current_session_id} not found in loaded sessions")
    return "無題のチャット"

def get_file_access_url(source_uri, document_name):
    """ファイルアクセスURLを取得（エラー処理強化版）"""
    # FILE_ACCESS_API が設定されていない場合は None を返す
    if not FILE_ACCESS_API:
        print("DEBUG: FILE_ACCESS_API not configured")
        return None
    
    # キャッシュキーを生成
    cache_key = f"file_url_{hash(source_uri)}_{hash(document_name)}"
    
    # セッション状態にファイルURLキャッシュがない場合は初期化
    if 'file_url_cache' not in st.session_state:
        st.session_state.file_url_cache = {}
    
    # キャッシュから取得を試行
    if cache_key in st.session_state.file_url_cache:
        cached_data = st.session_state.file_url_cache[cache_key]
        # キャッシュが5分以内の場合は使用
        if time.time() - cached_data['timestamp'] < 300:  # 5分
            print(f"DEBUG: Using cached file URL for {document_name}")
            return cached_data['url']
    
    try:
        print(f"DEBUG: Requesting file URL for {document_name} from {FILE_ACCESS_API}")
        response = requests.post(
            f"{FILE_ACCESS_API}/get-file-url",
            headers={
                'Authorization': f'Bearer {st.session_state.auth_token}',
                'Content-Type': 'application/json',
                'User-Agent': 'RAG-ChatBot/1.0'
            },
            json={
                "source_uri": source_uri,
                "document_name": document_name
            },
            timeout=10
        )
        
        if response.status_code == 200:
            file_url = response.json().get('file_url')
            # キャッシュに保存
            st.session_state.file_url_cache[cache_key] = {
                'url': file_url,
                'timestamp': time.time()
            }
            print(f"DEBUG: Successfully got file URL for {document_name}")
            return file_url
        else:
            print(f"DEBUG: File URL request failed with status {response.status_code}")
        return None
    except Exception as e:
        print(f"DEBUG: File URL request error: {str(e)}")
        return None

def show_auth_interface():
    """認証画面（未ログイン時のみ表示）"""
    # メインコンテンツ（認証画面）
    st.title("🤖 RAG ChatBot")
    st.caption("セキュアな知識ベース検索システム")
    
    st.header("🔐 ログイン・サインアップ")
    
    # ウェルカムメッセージ
    st.info("🎉 **RAG ChatBotへようこそ！**\n\n"
           "AI搭載の知識検索システムです。ログインまたはサインアップしてご利用ください。")
    
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
    
    # サイドバーを最小限に
    with st.sidebar:
        st.title("🔐 認証")
        
        # システム情報のみ表示
        with st.expander("ℹ️ システム情報"):
            st.write("**RAG ChatBot v1.0**")
            st.write("• セキュア認証システム")
            st.write("• 知識ベース検索")
            st.write("• チャット履歴管理")
        
        st.divider()
        st.caption("🔒 **セキュリティ保護されたシステム**")
        st.caption("認証されたユーザーのみアクセス可能")
    
    tab1, tab2 = st.tabs(["ログイン", "サインアップ"])
    
    with tab1:
        st.subheader("🔑 既存アカウントでログイン")
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
        st.subheader("👤 新規アカウント作成")
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
                # セッション状態を明示的にクリア・再初期化
                st.session_state.clear()
                st.session_state.authenticated = True
                st.session_state.auth_token = data["token"]
                st.session_state.user_id = email
                st.session_state.messages = []
                st.session_state.chat_sessions = []
                st.session_state.current_session_id = None
                st.session_state.filters = {}
                st.session_state.file_url_cache = {}
                
                print(f"DEBUG: Login successful for {email}")
                st.success("✅ ログインしました！")
                st.balloons()
                st.rerun()
            else:
                error_data = response.json()
                error_msg = error_data.get('error', 'Unknown error')
                
                # エラータイプ別の対応
                if "Invalid" in error_msg or "password" in error_msg.lower():
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

def signup_user(email, password):
    """サインアップ処理（JWT自動ログイン対応）"""
    with st.spinner("👤 アカウント作成中..."):
        try:
            response = requests.post(
                f"{AUTH_API}/signup", 
                json={"user_id": email, "password": password},
                timeout=15
            )
            
            if response.status_code == 201:
                data = response.json()
                st.success("✅ アカウントを作成しました！")
                st.balloons()
                
                # Lambda関数からJWTトークンを受け取って自動ログイン
                if data.get("token"):
                    st.info("🔄 自動ログイン中...")
                    time.sleep(1)  # ユーザーフィードバック用の短い遅延
                    
                    # セッション状態を明示的にクリア・再初期化
                    st.session_state.clear()
                    st.session_state.authenticated = True
                    st.session_state.auth_token = data["token"]
                    st.session_state.user_id = email
                    st.session_state.messages = []
                    st.session_state.chat_sessions = []
                    st.session_state.current_session_id = None
                    st.session_state.filters = {}
                    st.session_state.file_url_cache = {}
                    
                    print(f"DEBUG: Signup and auto-login successful for {email}")
                    st.success("🎉 サインアップ完了！チャット画面に移動します...")
                    time.sleep(1)
                    st.rerun()
                else:
                    # フォールバック：従来の手動ログイン案内
                    st.info("📧 アカウント作成完了！ログインタブからログインしてください")
                    
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
            print(f"Signup error: {str(e)}")  # デバッグ用

def show_chat_interface():
    """チャット画面（認証後のみ表示）"""
    try:
        # 初回のセッション一覧読み込み
        if not st.session_state.chat_sessions:
            print("DEBUG: Loading chat sessions for the first time")
            st.session_state.chat_sessions = load_chat_sessions(st.session_state.auth_token)
        
        # 現在のセッションタイトルを取得
        current_title = get_current_session_title(st.session_state.current_session_id, st.session_state.chat_sessions)
        print(f"DEBUG: Current session title: {current_title}")
        
    except Exception as e:
        st.error(f"🚨 show_chat_interface初期化エラー: {str(e)}")
        print(f"ERROR in show_chat_interface: {str(e)}")
        return

    # サイドバー：セッション管理
    with st.sidebar:
        st.title("🤖 RAG ChatBot")
        st.write(f"👤 ユーザー: {st.session_state.user_id}")
        
        # デバッグ情報（開発時のみ表示）
        if st.checkbox("🔧 デバッグ情報", key="debug_toggle"):
            with st.expander("🐛 デバッグ情報"):
                st.write(f"**Current session ID**: {st.session_state.current_session_id}")
                st.write(f"**Loaded sessions**: {len(st.session_state.chat_sessions)}")
                st.write(f"**Messages count**: {len(st.session_state.messages)}")
                st.write(f"**File cache entries**: {len(st.session_state.get('file_url_cache', {}))}")
                st.write(f"**FILE_ACCESS_API**: {'✅ 設定済み' if FILE_ACCESS_API else '❌ 未設定'}")
        
        # セキュリティ情報表示
        with st.expander("🔒 セキュリティ情報"):
            st.write("✅ セッション暗号化済み")
            st.write("✅ データ保護有効")
            st.write("⏰ セッション有効期限: 24時間")
        
        st.divider()
        
        # 検索フィルター設定
        st.subheader("🔍 検索フィルター")
        with st.expander("詳細フィルター"):
            # 製品名フィルター
            product_options = {
                "": "",
                "エレベーター": "elevator",
                "エスカレーター": "escalator"
            }
            product_ui = st.selectbox(
                "製品名",
                list(product_options.keys()),
                key="chat_product_selectbox"
            )
            product_value = product_options[product_ui]
            
            # 文書名フィルター
            document_options = {
                "": "",
                "取説(保守点検編)": "kelg-maintenance-inspection",
                "取説(運用管理編)": "kelg-operation-management", 
                "イエローブック": "yellow-book"
            }
            document_ui = st.selectbox(
                "文書名",
                list(document_options.keys()),
                key="chat_document_selectbox"
            )
            document_value = document_options[document_ui]
            
            # その他のフィルター
            model = st.text_input("モデル", key="chat_model_input", max_chars=100)
            category = st.text_input("カテゴリ", key="chat_category_input", max_chars=100)
            
            # 入力値のサニタイゼーション
            filters = {}
            if product_value:
                filters["product"] = sanitize_input(product_value)
            if document_value:
                filters["document-type"] = sanitize_input(document_value)
            if model:
                filters["model"] = sanitize_input(model)
            if category:
                filters["category"] = sanitize_input(category)
            
            st.session_state.filters = filters
            
            if filters:
                st.write("**適用中のフィルター:**")
                for k, v in filters.items():
                    if k == "product":
                        display_value = [k for k, val in product_options.items() if val == v][0] if v in product_options.values() else v
                    elif k == "document-type":
                        display_value = [k for k, val in document_options.items() if val == v][0] if v in document_options.values() else v
                    else:
                        display_value = v
                    st.write(f"• {k}: {display_value}")
        
        st.divider()
        
        # チャット履歴
        st.subheader("📚 チャット履歴")
        
        # チャット管理ボタン
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ 新規チャット", use_container_width=True, key="new_chat_btn"):
                st.session_state.current_session_id = None
                st.session_state.messages = []
                print("DEBUG: Started new chat")
                st.rerun()
        
        with col2:
            if st.button("🔄 履歴更新", use_container_width=True, key="refresh_history_btn"):
                with st.spinner("セッション一覧を更新中..."):
                    st.session_state.chat_sessions = load_chat_sessions(st.session_state.auth_token)
                print("DEBUG: Refreshed chat sessions")
                st.rerun()
        
        # 保存済セッション一覧
        if st.session_state.chat_sessions:
            st.write("**保存済セッション:**")
            for i, session in enumerate(st.session_state.chat_sessions):
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        # セッション情報のサニタイゼーション
                        session_title = sanitize_input(session.get('title', '無題のチャット'))
                        
                        # 現在選択中のセッションにはマーカーを追加
                        display_title = session_title
                        if session['session_id'] == st.session_state.current_session_id:
                            display_title = f"🔸 {session_title}"
                        
                        if st.button(
                            display_title,
                            key=f"session_load_{session['session_id'][:8]}{i}",
                            use_container_width=True
                        ):
                            st.session_state.current_session_id = session['session_id']
                            # メッセージのサニタイゼーション
                            sanitized_messages = []
                            for msg in session.get('messages', []):
                                sanitized_msg = {
                                    'role': sanitize_input(msg.get('role', '')),
                                    'content': sanitize_input(msg.get('content', '')),
                                    'timestamp': msg.get('timestamp', ''),
                                    'citations': [sanitize_input(c) for c in msg.get('citations', [])],
                                    'source_documents': msg.get('source_documents', [])
                                }
                                sanitized_messages.append(sanitized_msg)
                            st.session_state.messages = sanitized_messages
                            print(f"DEBUG: Loaded session {session['session_id']} with {len(sanitized_messages)} messages")
                            st.rerun()
                    
                    with col2:
                        if st.button("🗑️", key=f"session_delete_{session['session_id'][:8]}{i}"):
                            if delete_chat_session(session['session_id'], st.session_state.auth_token):
                                st.success("セッションを削除しました")
                                st.session_state.chat_sessions = load_chat_sessions(st.session_state.auth_token)
                                # 削除したセッションが現在のセッションの場合、新規チャットに切り替え
                                if session['session_id'] == st.session_state.current_session_id:
                                    st.session_state.current_session_id = None
                                    st.session_state.messages = []
                                st.rerun()
                            else:
                                st.error("削除に失敗しました")
        
        st.divider()
        
        # ログアウト
        if st.button("🚪 ログアウト", use_container_width=True, key="logout_btn"):
            # セッション状態を明示的にクリア
            st.session_state.clear()
            st.success("ログアウトしました")
            print("DEBUG: User logged out")
            st.rerun()

    # メインチャット画面
    st.title("🤖 RAG ChatBot")
    st.caption("セキュアな知識ベース検索システム")
    
    # セッションタイトル表示
    if st.session_state.current_session_id:
        st.header(f"💬 {current_title}")
    else:
        st.header("💬 新規チャット")
    
    # フィルター表示
    if st.session_state.filters:
        with st.expander("🔍 検索フィルターが適用されています", expanded=False):
            for k, v in st.session_state.filters.items():
                st.write(f"**{k}**: {v}")
    
    # チャット履歴表示（永続化対応）
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            # メッセージ内容の表示（既にサニタイゼーション済み）
            st.markdown(message["content"])
            
            # 引用情報の表示（永続化対応・st.link_button版）
            if message["role"] == "assistant" and message.get("citations"):
                # ExpanderのデフォルトはFalseに設定（自動展開しない）
                with st.expander("📚 参照文書", expanded=False):
                    source_docs = message.get("source_documents", [])
                    print(f"DEBUG: Processing {len(message['citations'])} citations with {len(source_docs)} source docs")
                    
                    for j, citation in enumerate(message["citations"], 1):
                        col1, col2 = st.columns([4, 1])
                        
                        with col1:
                            # 対応する文書の情報を取得
                            doc_info = source_docs[j-1] if j-1 < len(source_docs) else {}
                            source_uri = doc_info.get('source_uri', '')
                            document_name = doc_info.get('document_name', citation.replace('📄 ', ''))
                            
                            print(f"DEBUG: Processing citation {j}: {document_name}, URI: {source_uri}")
                            
                            # ファイルアクセス機能の処理
                            if source_uri and FILE_ACCESS_API:
                                # ファイルURLを取得（キャッシュ機能付き）
                                file_url = get_file_access_url(source_uri, document_name)
                                if file_url:
                                    # ユニークキーを設定して永続化
                                    button_key = f"file_link_{i}_{j}_{hash(source_uri)}"
                                    st.link_button(
                                        f"📄 {document_name}",
                                        file_url,
                                        help="クリックしてファイルを新しいタブで開く",
                                        key=button_key
                                    )
                                else:
                                    st.write(f"📄 {document_name} (アクセス不可)")
                            else:
                                # ファイルアクセス機能が無効の場合は通常表示
                                if not FILE_ACCESS_API:
                                    st.write(f"📄 {document_name} (ファイルアクセス機能未設定)")
                                else:
                                    st.write(citation)
                        
                        with col2:
                            # 関連度表示
                            score = doc_info.get('score', 0) if j-1 < len(source_docs) else 0
                            if score > 0:
                                st.metric("関連度", f"{score:.3f}", help="検索クエリとの関連度スコア")
            
            # タイムスタンプ
            if message.get("timestamp"):
                st.caption(f"🕒 {message['timestamp'][:19].replace('T', ' ')}")
    
    # ユーザー入力（永続化対応）
    if prompt := st.chat_input("質問を入力してください（最大5000文字）", key="main_chat_input"):
        # 入力値のサニタイゼーション
        sanitized_prompt = sanitize_input(prompt)
        
        # 入力値検証
        if not sanitized_prompt:
            st.error("有効な質問を入力してください。")
            st.stop()
        
        if len(sanitized_prompt) > 5000:
            st.error("質問が長すぎます（最大5000文字）。")
            st.stop()
        
        print(f"DEBUG: User input: {sanitized_prompt[:50]}...")
        
        # ユーザーメッセージをセッション状態に追加
        user_message = {
            "role": "user", 
            "content": sanitized_prompt,
            "timestamp": datetime.now().isoformat()
        }
        st.session_state.messages.append(user_message)
        
        # ユーザーメッセージ表示
        with st.chat_message("user"):
            st.markdown(sanitized_prompt)
        
        # RAG APIコール（st.rerun()を使わない版）
        with st.chat_message("assistant"):
            with st.spinner("🤖 AI回答を生成中..."):
                response_data = call_rag_api(
                    sanitized_prompt, 
                    st.session_state.auth_token,
                    st.session_state.current_session_id,
                    st.session_state.filters
                )
                
                print(f"DEBUG: RAG API response received: {bool(response_data)}")
                
                if response_data and not response_data.get("error"):
                    # 回答表示
                    reply = response_data.get("reply", "回答を取得できませんでした")
                    st.markdown(reply)
                    
                    # 新規セッションの場合、セッションIDを更新
                    if response_data.get("is_new_session"):
                        old_session_id = st.session_state.current_session_id
                        st.session_state.current_session_id = response_data["session_id"]
                        session_title = response_data.get('title', '無題')
                        
                        print(f"DEBUG: New session created: {st.session_state.current_session_id}, title: {session_title}")
                        st.success(f"✨ 新しいセッション「{session_title}」を開始しました")
                        
                        # セッション一覧を更新（バックグラウンドで）
                        try:
                            st.session_state.chat_sessions = load_chat_sessions(st.session_state.auth_token)
                            print("DEBUG: Session list updated after new session creation")
                        except Exception as e:
                            print(f"DEBUG: Failed to update session list: {str(e)}")
                    
                    # 引用情報表示（永続化対応）
                    citations = response_data.get("citations", [])
                    source_docs = response_data.get("source_documents", [])
                    
                    print(f"DEBUG: Response has {len(citations)} citations and {len(source_docs)} source docs")
                    
                    # アシスタントメッセージをセッション状態に追加
                    assistant_message = {
                        "role": "assistant", 
                        "content": reply,
                        "timestamp": datetime.now().isoformat(),
                        "citations": citations,
                        "source_documents": source_docs
                    }
                    st.session_state.messages.append(assistant_message)
                    
                    if citations:
                        with st.expander("📚 参照文書", expanded=True):  # 新しい回答では展開状態で表示
                            for j, citation in enumerate(citations, 1):
                                col1, col2 = st.columns([4, 1])
                                
                                with col1:
                                    # 対応する文書の情報を取得
                                    doc_info = source_docs[j-1] if j-1 < len(source_docs) else {}
                                    source_uri = doc_info.get('source_uri', '')
                                    document_name = doc_info.get('document_name', citation.replace('📄 ', ''))
                                    
                                    print(f"DEBUG: New response citation {j}: {document_name}, URI: {source_uri}")
                                    
                                    # ファイルアクセス機能の処理
                                    if source_uri and FILE_ACCESS_API:
                                        # ファイルURLを取得（キャッシュ機能付き）
                                        file_url = get_file_access_url(source_uri, document_name)
                                        if file_url:
                                            # 新しい回答の場合は特別なキーを使用
                                            button_key = f"new_file_link_{j}_{int(time.time())}"
                                            st.link_button(
                                                f"📄 {document_name}",
                                                file_url,
                                                help="クリックしてファイルを新しいタブで開く",
                                                key=button_key
                                            )
                                        else:
                                            st.write(f"📄 {document_name} (アクセス不可)")
                                    else:
                                        # ファイルアクセス機能が無効の場合は通常表示
                                        if not FILE_ACCESS_API:
                                            st.write(f"📄 {document_name} (ファイルアクセス機能未設定)")
                                        else:
                                            st.write(citation)
                                
                                with col2:
                                    # 関連度表示
                                    score = doc_info.get('score', 0) if j-1 < len(source_docs) else 0
                                    if score > 0:
                                        st.metric("関連度", f"{score:.3f}", help="検索クエリとの関連度スコア")
                        
                        st.success("✅ 回答を生成しました（参照文書付き）")
                    else:
                        st.success("✅ 回答を生成しました")
                    
                else:
                    # エラー処理
                    error_msg = response_data.get("error", "申し訳ございませんが、現在回答を生成できません。しばらく後に再試行してください。") if response_data else "API接続エラーが発生しました。"
                    st.error(f"❌ エラー: {error_msg}")
                    print(f"DEBUG: RAG API error: {error_msg}")
                    
                    # エラーメッセージもセッション状態に保存
                    error_message = {
                        "role": "assistant", 
                        "content": error_msg,
                        "timestamp": datetime.now().isoformat()
                    }
                    st.session_state.messages.append(error_message)

def main():
    # セッション状態の初期化
    if 'auth_token' not in st.session_state:
        # URL パラメータからトークン取得を試行
        query_params = st.experimental_get_query_params()
        token = query_params.get('token', [None])[0]
        st.session_state.auth_token = token
    if 'current_session_id' not in st.session_state:
        st.session_state.current_session_id = None
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'chat_sessions' not in st.session_state:
        st.session_state.chat_sessions = []
    if 'filters' not in st.session_state:
        st.session_state.filters = {}
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'file_url_cache' not in st.session_state:
        st.session_state.file_url_cache = {}
    
    print(f"DEBUG: Session state initialized, authenticated: {st.session_state.authenticated}")
    
    # 認証チェック
    if st.session_state.auth_token:
        user_id = verify_jwt_token(st.session_state.auth_token)
        if user_id:
            st.session_state.user_id = user_id
            st.session_state.authenticated = True
            print(f"DEBUG: Token verified for user: {user_id}")
        else:
            st.session_state.auth_token = None
            st.session_state.authenticated = False
            print("DEBUG: Token verification failed")
    
    # 認証状態によって画面切り替え
    if st.session_state.authenticated:
        show_chat_interface()
    else:
        show_auth_interface()

def call_rag_api(query, token, session_id, filters):
    """RAG APIの呼び出し（セキュリティ対策付き）"""
    try:
        # リクエストペイロードの構築
        payload = {
            "message": query,
            "filters": filters
        }
        
        if session_id:
            payload["session_id"] = session_id
        
        print(f"DEBUG: Calling RAG API with session_id: {session_id}, filters: {filters}")
        
        # APIリクエスト実行
        response = requests.post(
            f"{RAG_API}/query",
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'User-Agent': 'RAG-ChatBot/1.0'
            },
            json=payload,
            timeout=180,  # 3分タイムアウト
            verify=True   # SSL証明書検証
        )
        
        print(f"DEBUG: RAG API response status: {response.status_code}")
        
        # レスポンス処理
        if response.status_code == 200:
            response_data = response.json()
            
            # レスポンスデータのサニタイゼーション
            if 'reply' in response_data:
                response_data['reply'] = sanitize_input(response_data['reply'])
            
            if 'citations' in response_data:
                sanitized_citations = []
                for citation in response_data['citations']:
                    sanitized_citations.append(sanitize_input(citation))
                response_data['citations'] = sanitized_citations
            
            print(f"DEBUG: RAG API success, new session: {response_data.get('is_new_session', False)}")
            return response_data
        
        elif response.status_code == 401:
            return {"error": "認証が無効です。再度ログインしてください。"}
        elif response.status_code == 403:
            return {"error": "アクセス権限がありません。"}
        elif response.status_code == 429:
            return {"error": "リクエストが多すぎます。しばらく待ってから再試行してください。"}
        else:
            return {"error": f"APIエラー（ステータス: {response.status_code}）"}
            
    except requests.exceptions.Timeout:
        return {"error": "⏰ 回答の生成に時間がかかりすぎました。もう一度お試しください。"}
    except requests.exceptions.SSLError:
        return {"error": "🔒 SSL証明書エラーが発生しました。"}
    except requests.exceptions.ConnectionError:
        return {"error": "🌐 ネットワーク接続エラーが発生しました。"}
    except Exception as e:
        print(f"DEBUG: RAG API call exception: {str(e)}")
        return {"error": "❌ 予期しないエラーが発生しました。"}

if __name__ == "__main__":
    main()
