import streamlit as st
import requests
import json
import os
import uuid
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
        
        # セッション状態デバッグ
        with st.sidebar.expander("セッション状態"):
            st.json({
                "authenticated": st.session_state.get('authenticated', False),
                "user_id": st.session_state.get('user_id'),
                "current_session_id": st.session_state.get('current_session_id'),
                "messages_count": len(st.session_state.get('messages', [])),
                "chat_sessions_count": len(st.session_state.get('chat_sessions', []))
            })
    
    # セッション状態の初期化  
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'token' not in st.session_state:
        st.session_state.token = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'current_session_id' not in st.session_state:
        st.session_state.current_session_id = None
    if 'chat_sessions' not in st.session_state:
        st.session_state.chat_sessions = []
    if 'pending_login' not in st.session_state:
        st.session_state.pending_login = False
    if 'search_filters' not in st.session_state:
        st.session_state.search_filters = {}
    if 'filters_enabled' not in st.session_state:
        st.session_state.filters_enabled = False
    
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
    # チャット履歴を読み込み（初回のみ）
    if not st.session_state.chat_sessions:
        load_chat_sessions()
    
    # サイドバー
    with st.sidebar:
        st.write(f"👤 **ユーザー**: {st.session_state.user_id}")
        st.write(f"🔑 **認証状態**: ✅ 認証済み")
        
        # 現在のセッション情報
        if st.session_state.current_session_id:
            st.write(f"💬 **現在のセッション**: {st.session_state.current_session_id[:8]}...")
        else:
            st.write("💬 **現在のセッション**: 新規")
        
        if st.button("🚪 ログアウト", use_container_width=True):
            logout_user()
        
        st.divider()
        
        # チャット管理
        st.subheader("💬 チャット管理")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ 新しいチャット", use_container_width=True):
                start_new_chat()
        
        with col2:
            if st.button("🔄 履歴更新", use_container_width=True):
                load_chat_sessions()
        
        st.write(f"📝 **現在のメッセージ数**: {len(st.session_state.messages)}")
        st.write(f"📚 **保存済セッション数**: {len(st.session_state.chat_sessions)}")
        
        # チャット履歴一覧
        if st.session_state.chat_sessions:
            st.subheader("📚 過去のチャット")
            for i, session in enumerate(st.session_state.chat_sessions):
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    
                    with col1:
                        session_title = session.get('title', '無題のチャット')[:30]
                        message_count = session.get('message_count', 0)
                        session_info = f"{session_title}\n({message_count}メッセージ)"
                        
                        if st.button(
                            session_info,
                            key=f"load_session_{i}",
                            use_container_width=True
                        ):
                            load_session(session['session_id'])
                    
                    with col2:
                        if st.button("🗑️", key=f"delete_session_{i}"):
                            delete_session(session['session_id'])
        else:
            st.info("📝 まだチャット履歴がありません")
        
        # セキュリティ情報
        with st.expander("🛡️ セキュリティステータス"):
            st.write("🔐 **JWT認証**: 有効")  
            st.write("⚡ **レート制限**: 有効")
            st.write("🌐 **CORS保護**: 有効")
            st.write("🛡️ **Gateway Response**: 設定済み")
            st.write("🔒 **HTTPS通信**: 有効")
        
        st.divider()
        
        # 絞り込み検索設定
        st.subheader("🔍 絞り込み検索")
        
        # フィルター有効化チェックボックス
        filters_enabled = st.checkbox(
            "🎯 絞り込み検索を有効化",
            value=st.session_state.filters_enabled,
            help="特定の文書タイプや製品に絞って検索できます"
        )
        st.session_state.filters_enabled = filters_enabled
        
        if filters_enabled:
            with st.container():
                # 製品フィルター（指定された内容）
                product_options = {
                    "": "",
                    "エレベーター": "elevator",
                    "エスカレーター": "escalator"
                }
                
                product_display = st.selectbox(
                    "🏭 製品名",
                    options=list(product_options.keys()),
                    index=0,
                    help="検索対象の製品を選択",
                    key="filter_product"
                )
                product_value = product_options[product_display]
                
                # 文書名フィルター（指定された内容）
                document_options = {
                    "": "",
                    "取説(保守点検編)": "kelg-maintenance-inspection",
                    "取説(運用管理編)": "kelg-operation-management", 
                    "イエローブック": "yellow-book"
                }
                
                document_display = st.selectbox(
                    "📄 文書名",
                    options=list(document_options.keys()),
                    index=0,
                    help="検索対象の文書を選択",
                    key="filter_document"
                )
                document_value = document_options[document_display]
                
                # 追加フィルター（既存の機能も保持）
                with st.expander("🔧 詳細フィルター", expanded=False):
                    # モデルフィルター
                    model = st.text_input(
                        "🔧 モデル/型番",
                        placeholder="例: HVF-2000, TSE-301",
                        help="機器のモデルや型番で絞り込み",
                        key="filter_model",
                        max_chars=100
                    )
                    
                    # カテゴリフィルター
                    category = st.selectbox(
                        "📋 カテゴリ",
                        options=["", "safety", "maintenance", "operation", "installation", "troubleshooting", "inspection"],
                        index=0,
                        help="文書のカテゴリで絞り込み",
                        key="filter_category"
                    )
                    
                    # 部門フィルター
                    department = st.selectbox(
                        "🏢 部門",
                        options=["", "engineering", "maintenance", "sales", "support", "quality", "safety"],
                        index=0,
                        help="担当部門で絞り込み",
                        key="filter_department"
                    )
                
                # フィルター設定の更新
                current_filters = {}
                if product_value:
                    current_filters["product"] = product_value
                if document_value:
                    current_filters["document-type"] = document_value
                if model.strip():
                    current_filters["model"] = model.strip()
                if category:
                    current_filters["category"] = category
                if department:
                    current_filters["department"] = department
                
                st.session_state.search_filters = current_filters
                
                # 現在のフィルター表示（わかりやすく表示）
                if current_filters:
                    st.write("**🎯 適用中のフィルター:**")
                    
                    # メインフィルターを強調表示
                    if product_value:
                        st.success(f"🏭 **製品**: {product_display}")
                    if document_value:
                        st.success(f"📄 **文書**: {document_display}")
                    
                    # 詳細フィルターがあれば表示
                    detail_filters = []
                    if model.strip():
                        detail_filters.append(f"🔧 モデル: `{model}`")
                    if category:
                        detail_filters.append(f"📋 カテゴリ: `{category}`")
                    if department:
                        detail_filters.append(f"🏢 部門: `{department}`")
                    
                    if detail_filters:
                        st.write("**詳細フィルター:**")
                        for detail in detail_filters:
                            st.write(f"• {detail}")
                    
                    # フィルタークリアボタン
                    if st.button("🗑️ フィルターをクリア", use_container_width=True):
                        st.session_state.search_filters = {}
                        st.session_state.filters_enabled = False
                        st.rerun()
                else:
                    st.info("💡 フィルターを設定すると、より精密な検索ができます")
                    
                    # フィルター機能の説明（更新版）
                    with st.expander("📖 絞り込み検索の使い方", expanded=False):
                        st.markdown("""
                        **🎯 絞り込み検索機能について**
                        
                        この機能を使用すると、特定の条件に合致する文書のみを検索対象にできます。
                        
                        **🏭 製品選択:**
                        - **エレベーター**: エレベーター関連の全文書
                        - **エスカレーター**: エスカレーター関連の全文書
                        
                        **📄 文書選択:**
                        - **取説(保守点検編)**: 保守・点検に関する取扱説明書
                        - **取説(運用管理編)**: 運用・管理に関する取扱説明書
                        - **イエローブック**: イエローブック（故障対応等）
                        
                        **💡 使用例:**
                        1. **エレベーターの保守点検について調べたい**
                           → 製品: `エレベーター`, 文書: `取説(保守点検編)`
                        2. **エスカレーターの運用管理を確認したい**
                           → 製品: `エスカレーター`, 文書: `取説(運用管理編)`
                        3. **故障時の対応方法を調べたい**
                           → 文書: `イエローブック`
                        """)
        else:
            # フィルター無効時はクリア
            st.session_state.search_filters = {}
            st.info("🔍 絞り込み検索を有効にすると、特定の条件で文書を検索できます")
            
            # 簡単な機能紹介（更新版）
            with st.expander("🔍 絞り込み検索とは？", expanded=False):
                st.markdown("""
                **🎯 絞り込み検索機能**
                
                エレベーター・エスカレーターの文書から、あなたが本当に必要な情報だけを効率的に見つけることができます。
                
                **対象文書:**
                - 📄 **取説(保守点検編)**: 保守・点検作業のマニュアル
                - 📄 **取説(運用管理編)**: 日常運用・管理のガイド
                - 📄 **イエローブック**: 故障対応・トラブルシューティング
                
                **対象製品:**
                - 🏭 **エレベーター**: 全エレベーター関連文書
                - 🏭 **エスカレーター**: 全エスカレーター関連文書
                
                **メリット:**
                - ⚡ **検索速度向上**: 関連文書のみを対象にするため高速
                - 🎯 **精度向上**: より関連性の高い回答を取得
                - 📚 **効率的**: 不要な情報を除外して集中的な回答
                
                上のチェックボックスを有効にして試してみてください！
                """)
    
    # メインチャット画面
    st.header("💬 AIチャット")
    
    # フィルター適用状況の表示
    if st.session_state.filters_enabled and st.session_state.search_filters:
        with st.container():
            st.info("🎯 **絞り込み検索が有効です**")
            
            # フィルター情報を分かりやすく表示
            filter_cols = st.columns(len(st.session_state.search_filters))
            for i, (key, value) in enumerate(st.session_state.search_filters.items()):
                with filter_cols[i]:
                    # 表示名の変換
                    display_label = key
                    display_value = value
                    
                    if key == "product":
                        display_label = "製品"
                        display_value = "エレベーター" if value == "elevator" else "エスカレーター" if value == "escalator" else value
                    elif key == "document-type":
                        display_label = "文書"
                        doc_names = {
                            "kelg-maintenance-inspection": "取説(保守点検編)",
                            "kelg-operation-management": "取説(運用管理編)", 
                            "yellow-book": "イエローブック"
                        }
                        display_value = doc_names.get(value, value)
                    
                    st.metric(
                        label=display_label,
                        value=display_value,
                        help=f"検索対象: {key} = {value}"
                    )
    
    elif st.session_state.filters_enabled:
        st.warning("⚠️ 絞り込み検索が有効ですが、フィルターが設定されていません")
    
    # ウェルカムメッセージ
    if not st.session_state.messages:
        with st.chat_message("assistant"):
            welcome_message = """
            👋 **RAG ChatBotへようこそ！**
            
            私は知識ベースを検索して、正確で引用付きの回答を提供します。
            
            **できること：**
            - 📚 文書検索・要約
            - 💡 質問への詳細回答  
            - 🔍 情報の出典表示
            - 💬 自然な対話
            - 🎯 絞り込み検索（サイドバーで設定）
            
            **絞り込み検索機能：**
            - 📄 文書タイプ別検索
            - 🏭 製品・モデル別検索  
            - 📋 カテゴリ・部門別検索
            
            何でもお気軽にお聞きください！🤖✨
            """
            
            if st.session_state.filters_enabled:
                welcome_message += "\n\n🎯 **現在絞り込み検索が有効です**"
            
            st.markdown(welcome_message)
    
    # チャット履歴表示
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # アシスタントメッセージの追加情報
            if message["role"] == "assistant":
                if "timestamp" in message:
                    st.caption(f"🕒 {message['timestamp']}")
                
                # 引用情報表示（改善版）
                if "citations" in message and message["citations"]:
                    with st.expander("📚 参照文書", expanded=False):
                        for i, citation in enumerate(message["citations"], 1):
                            st.write(f"{i}. {citation}")
                
                # 詳細文書情報表示（入れ子を避けた設計）
                if "source_documents" in message and message["source_documents"]:
                    with st.expander("📄 詳細文書情報", expanded=False):
                        for i, doc in enumerate(message["source_documents"], 1):
                            st.subheader(f"文書 {i}")
                            
                            # 文書メタ情報
                            doc_name = doc.get('document_name', 'N/A')
                            doc_type = doc.get('document_type', 'N/A')
                            product = doc.get('product', 'N/A')
                            score = doc.get('score', 0)
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**文書名**: {doc_name}")
                                st.write(f"**タイプ**: {doc_type}")
                            with col2:
                                st.write(f"**製品**: {product}")
                                st.write(f"**関連度**: {score:.3f}")
                            
                            # 文書内容（expanderの入れ子を避けてそのまま表示）
                            if 'content' in doc and doc['content'].strip():
                                st.write("**📖 文書内容:**")
                                # 文書内容を制限付きで表示
                                content = doc['content'][:2000]
                                if len(doc['content']) > 2000:
                                    content += "\n\n... (内容が長いため一部省略)"
                                
                                st.text_area(
                                    f"📄 {doc_name}",
                                    content,
                                    height=200,
                                    key=f"doc_content_{i}_{hash(str(message.get('timestamp', '')))}",
                                    help="文書の内容を表示しています。全文を確認したい場合は元の文書を参照してください。"
                                )
                            
                            if i < len(message["source_documents"]):
                                st.divider()
    
    # ユーザー入力
    # フィルター状況に応じたプレースホルダー
    if st.session_state.filters_enabled and st.session_state.search_filters:
        placeholder_text = f"💬 質問を入力してください...（{len(st.session_state.search_filters)}個のフィルター適用中）"
    else:
        placeholder_text = "💬 質問を入力してください..."
    
    if prompt := st.chat_input(placeholder_text):
        # 入力値検証
        if len(prompt.strip()) == 0:
            st.error("質問を入力してください")
            return
            
        if len(prompt) > 1000:
            st.error("質問が長すぎます（1000文字以内）")
            return
        
        # フィルター警告表示
        if st.session_state.filters_enabled and not st.session_state.search_filters:
            st.warning("⚠️ 絞り込み検索が有効ですが、フィルターが設定されていません。全ての文書が検索対象になります。")
        
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
                    
                    # セッションIDの更新（新規セッション作成時）
                    if response.get("session_id") and not st.session_state.current_session_id:
                        st.session_state.current_session_id = response["session_id"]
                        st.success(f"✨ 新しいセッション「{response.get('title', '新規チャット')}」を開始しました")
                    
                    # 引用情報表示
                    citations_displayed = False
                    if response.get("citations"):
                        with st.expander("📚 参照文書", expanded=False):
                            for i, citation in enumerate(response["citations"], 1):
                                st.write(f"{i}. {citation}")
                        citations_displayed = True
                    
                    # 詳細文書情報表示
                    source_docs_displayed = False
                    if response.get("source_documents"):
                        with st.expander("📄 詳細文書情報", expanded=False):
                            # フィルター適用情報
                            if st.session_state.filters_enabled and st.session_state.search_filters:
                                st.info(f"🎯 以下の結果は絞り込み検索により取得されました")
                                filter_summary = ", ".join([f"{k}={v}" for k, v in st.session_state.search_filters.items()])
                                st.caption(f"適用フィルター: {filter_summary}")
                                st.divider()
                            
                            for i, doc in enumerate(response["source_documents"], 1):
                                st.subheader(f"文書 {i}")
                                
                                doc_name = doc.get('document_name', 'N/A')
                                doc_type = doc.get('document_type', 'N/A')
                                product = doc.get('product', 'N/A')
                                score = doc.get('score', 0)
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**文書名**: {doc_name}")
                                    st.write(f"**タイプ**: {doc_type}")
                                with col2:
                                    st.write(f"**製品**: {product}")
                                    st.write(f"**関連度**: {score:.3f}")
                                
                                # フィルター条件との一致を表示
                                if st.session_state.filters_enabled and st.session_state.search_filters:
                                    matches = []
                                    
                                    # 製品フィルターの一致確認
                                    if "product" in st.session_state.search_filters:
                                        filter_product = st.session_state.search_filters["product"]
                                        doc_product = doc.get('product', '')
                                        product_name = "エレベーター" if filter_product == "elevator" else "エスカレーター" if filter_product == "escalator" else filter_product
                                        
                                        if filter_product.lower() in str(doc_product).lower():
                                            matches.append(f"✅ 製品: {product_name} ({doc_product})")
                                        else:
                                            matches.append(f"❌ 製品: {product_name} (実際: {doc_product})")
                                    
                                    # 文書タイプフィルターの一致確認
                                    if "document-type" in st.session_state.search_filters:
                                        filter_doc_type = st.session_state.search_filters["document-type"]
                                        doc_doc_type = doc.get('document_type', '')
                                        
                                        # 文書名の表示名を取得
                                        doc_type_names = {
                                            "kelg-maintenance-inspection": "取説(保守点検編)",
                                            "kelg-operation-management": "取説(運用管理編)",
                                            "yellow-book": "イエローブック"
                                        }
                                        doc_name = doc_type_names.get(filter_doc_type, filter_doc_type)
                                        
                                        if filter_doc_type.lower() in str(doc_doc_type).lower():
                                            matches.append(f"✅ 文書: {doc_name} ({doc_doc_type})")
                                        else:
                                            matches.append(f"❌ 文書: {doc_name} (実際: {doc_doc_type})")
                                    
                                    # その他のフィルターの一致確認
                                    for filter_key, filter_value in st.session_state.search_filters.items():
                                        if filter_key not in ["product", "document-type"]:
                                            doc_value = doc.get(filter_key.replace('-', '_'), '')
                                            if filter_value.lower() in str(doc_value).lower():
                                                matches.append(f"✅ {filter_key}: {filter_value} ({doc_value})")
                                            else:
                                                matches.append(f"❌ {filter_key}: {filter_value} (実際: {doc_value})")
                                    
                                    if matches:
                                        st.write("**🎯 フィルター条件との一致:**")
                                        for match in matches:
                                            st.write(f"  {match}")
                                
                                if i < len(response["source_documents"]):
                                    st.divider()
                        source_docs_displayed = True
                    
                    # アシスタントメッセージ追加
                    assistant_message = {
                        "role": "assistant", 
                        "content": response["reply"],
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "citations": response.get("citations", []),
                        "source_documents": response.get("source_documents", [])
                    }
                    st.session_state.messages.append(assistant_message)
                    
                    # 新規セッションの場合はチャット履歴を更新
                    if response.get("is_new_session"):
                        load_chat_sessions()
                    
                    # 成功メッセージ
                    if citations_displayed or source_docs_displayed:
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
    """ログイン処理（修正版）"""
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
                st.session_state.pending_login = True
                
                st.success("✅ ログインしました！")
                st.balloons()
                
                # チャット履歴を読み込み
                load_chat_sessions()
                
                # 強制的にページを更新
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
            st.error(f"詳細: {str(e)}")

def signup_user(email, password):
    """サインアップ処理（修正版）"""
    with st.spinner("👤 アカウント作成中..."):
        try:
            response = requests.post(
                f"{AUTH_API}/signup", 
                json={"user_id": email, "password": password},
                timeout=15
            )
            
            if response.status_code == 201:
                st.success("✅ アカウントを作成しました！")
                st.info("🔄 自動的にログインしています...")
                
                # 自動ログイン
                auto_login_response = requests.post(
                    f"{AUTH_API}/login",
                    json={"user_id": email, "password": password},
                    timeout=15
                )
                
                if auto_login_response.status_code == 200:
                    data = auto_login_response.json()
                    st.session_state.authenticated = True
                    st.session_state.token = data["token"]
                    st.session_state.user_id = email
                    
                    st.success("✅ 自動ログインしました！チャット画面に移動します")
                    st.balloons()
                    
                    # チャット履歴を読み込み
                    load_chat_sessions()
                    
                    # 強制的にページを更新
                    st.rerun()
                else:
                    st.success("✅ アカウント作成完了！ログインタブからログインしてください")
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

def logout_user():
    """ログアウト処理"""
    st.session_state.authenticated = False
    st.session_state.token = None
    st.session_state.user_id = None
    st.session_state.messages = []
    st.session_state.current_session_id = None
    st.session_state.chat_sessions = []
    st.session_state.pending_login = False
    
    st.success("✅ ログアウトしました")
    st.rerun()

def start_new_chat():
    """新しいチャット開始"""
    st.session_state.messages = []
    st.session_state.current_session_id = None
    st.success("✨ 新しいチャットを開始しました")
    st.rerun()

def load_chat_sessions():
    """チャット履歴読み込み"""
    if not st.session_state.token:
        return
    
    try:
        response = requests.get(
            f"{CHAT_API}/sessions",
            headers={"Authorization": f"Bearer {st.session_state.token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.chat_sessions = data.get("sessions", [])
        else:
            st.warning("⚠️ チャット履歴の読み込みに失敗しました")
            
    except Exception as e:
        st.warning(f"⚠️ チャット履歴読み込みエラー: {str(e)}")

def load_session(session_id):
    """セッション読み込み"""
    # 現在のセッションIDを更新
    st.session_state.current_session_id = session_id
    
    # セッションからメッセージを復元
    for session in st.session_state.chat_sessions:
        if session['session_id'] == session_id:
            st.session_state.messages = session.get('messages', [])
            break
    
    st.success(f"✅ セッション {session_id[:8]}... を読み込みました")
    st.rerun()

def delete_session(session_id):
    """セッション削除"""
    try:
        response = requests.delete(
            f"{CHAT_API}/sessions/{session_id}",
            headers={"Authorization": f"Bearer {st.session_state.token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            st.success("🗑️ セッションを削除しました")
            
            # 削除されたセッションが現在のセッションの場合、新規チャットに切り替え
            if st.session_state.current_session_id == session_id:
                start_new_chat()
            else:
                # チャット履歴を再読み込み
                load_chat_sessions()
                st.rerun()
        else:
            st.error("❌ セッションの削除に失敗しました")
            
    except Exception as e:
        st.error(f"❌ 削除エラー: {str(e)}")

def call_rag_api(query):
    """RAG API呼び出し（絞り込み検索対応版）"""
    try:
        # リクエストペイロード作成
        payload = {"message": query}
        
        # 現在のセッションIDがある場合は含める
        if st.session_state.current_session_id:
            payload["session_id"] = st.session_state.current_session_id
        
        # 絞り込み検索フィルターを追加
        if st.session_state.filters_enabled and st.session_state.search_filters:
            payload["filters"] = st.session_state.search_filters
            
            # デバッグ情報表示（適用フィルターの確認）
            with st.expander("🔧 送信されたフィルター情報", expanded=False):
                st.write("**適用されたフィルター:**")
                for key, value in st.session_state.search_filters.items():
                    display_key = key
                    display_value = value
                    
                    if key == "product":
                        display_key = "製品 (product)"
                        display_value = f"{value} ({'エレベーター' if value == 'elevator' else 'エスカレーター' if value == 'escalator' else value})"
                    elif key == "document-type":
                        display_key = "文書タイプ (document-type)"
                        doc_names = {
                            "kelg-maintenance-inspection": "取説(保守点検編)",
                            "kelg-operation-management": "取説(運用管理編)",
                            "yellow-book": "イエローブック"
                        }
                        display_name = doc_names.get(value, value)
                        display_value = f"{value} ({display_name})"
                    
                    st.write(f"• **{display_key}**: `{display_value}`")
                
                st.json(st.session_state.search_filters)
        
        response = requests.post(
            f"{RAG_API}/query",
            json=payload,
            headers={"Authorization": f"Bearer {st.session_state.token}"},
            timeout=60  # RAG処理は時間がかかる可能性
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # フィルター適用結果の情報表示
            if st.session_state.filters_enabled and st.session_state.search_filters:
                filter_info = f"🎯 絞り込み検索適用済み ({len(st.session_state.search_filters)}件のフィルター)"
                st.success(filter_info)
            
            return result
        elif response.status_code == 401:
            st.error("🔐 認証が切れました。再度ログインしてください")
            logout_user()
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
