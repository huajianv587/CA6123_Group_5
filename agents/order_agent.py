"""
订单 Agent：仅通过 Supabase 访问 orders + order_addresses（团队 schema）。

须配置 SUPABASE_URL 与密钥；未配置则在初始化时抛出 RuntimeError。
"""
import re
from typing import Any, Dict, List, Optional
from datetime import datetime
from .base_agent import BaseAgent, Message, AgentResponse, IntentType
from .supabase_order_repository import SupabaseOrderRepository


class OrderAgent(BaseAgent):

    def __init__(self):
        super().__init__("order", "OrderAgent")
        self._repo = SupabaseOrderRepository.from_env()
        if not self._repo:
            raise RuntimeError(
                "OrderAgent 仅使用数据库：请配置环境变量 SUPABASE_URL 以及 "
                "SUPABASE_SERVICE_ROLE_KEY / SUPABASE_PUBLISHABLE_KEY / SUPABASE_ANON_KEY 之一。"
            )
        self.log("订单数据源：Supabase（orders + order_addresses）")
        self._pending_address_by_session: Dict[str, str] = {}

    def _get_order(self, order_id: Optional[str]) -> Optional[Dict]:
        if not order_id:
            return None
        return self._repo.fetch_by_order_id(order_id)

    def _list_recent_orders(self, limit: int = 2) -> List[Dict]:
        return self._repo.fetch_recent(limit)

    def _list_all_orders(self) -> List[Dict]:
        return self._repo.fetch_all(100)

    def process(self, message: Message) -> AgentResponse:
        content = message.content
        data = message.data
        extracted: Dict[str, Any] = data.get("extracted_data") or {}
        order_id = extracted.get("order_id")
        sid = message.session_id or ""
        self.log(f"处理订单请求: {content}")

        addr_kw = ["改地址", "换地址", "修改地址"]
        has_addr_kw = any(kw in content for kw in addr_kw)

        if sid and sid in self._pending_address_by_session:
            p_oid = self._pending_address_by_session[sid]
            parsed = self._parse_new_address_from_user_text(content, extracted)
            if parsed and not has_addr_kw:
                order = self._get_order(p_oid)
                if order and order.get("can_modify_address"):
                    return self._apply_address_update(p_oid, order, parsed, sid)

        if has_addr_kw:
            return self._handle_address_change(order_id, content, extracted, sid)
        if any(kw in content for kw in ["取消", "不要了"]):
            if sid:
                self._pending_address_by_session.pop(sid, None)
            return self._handle_cancel_order(order_id, content)
        if any(kw in content for kw in ["所有", "全部", "列表"]):
            return self._handle_list_orders()
        return self._handle_query_order(order_id, content)

    def _handle_query_order(self, order_id: Optional[str], content: str) -> AgentResponse:
        if order_id:
            order = self._get_order(order_id)
            if order:
                return AgentResponse(
                    success=True,
                    message=self._format_order_info(order),
                    data={"order": order, "action": "query"},
                )
            return AgentResponse(
                success=False,
                message=f"未找到订单号 {order_id} 的信息，请确认订单号是否正确。",
                data={"action": "query", "order_id": order_id},
            )
        recent = self._list_recent_orders(2)
        if not recent:
            return AgentResponse(
                success=True,
                message="未指定订单号；数据库中暂无订单记录。",
                data={"orders": [], "action": "list_recent"},
            )
        msg = "未指定订单号，为您查询最近的订单：\n\n"
        for o in recent:
            msg += self._format_order_brief(o) + "\n---\n"
        msg += "\n如需查询特定订单，请提供订单号。"
        return AgentResponse(success=True, message=msg, data={"orders": recent, "action": "list_recent"})

    def _handle_address_change(
        self,
        order_id: Optional[str],
        content: str,
        extracted: Dict[str, Any],
        session_id: str,
    ) -> AgentResponse:
        if not order_id:
            m = re.search(r"订单[号编号]?\s*(\d{10,20})", content)
            if m:
                order_id = m.group(1)
        if not order_id:
            return AgentResponse(
                success=False,
                message="修改地址需要提供订单号，请提供您要修改的订单号。",
                data={"action": "change_address", "need_info": "order_id"},
            )
        order = self._get_order(order_id)
        if not order:
            return AgentResponse(
                success=False,
                message=f"未找到订单号 {order_id}，请确认是否正确。",
                data={"action": "change_address", "order_id": order_id},
            )
        if not order["can_modify_address"]:
            if session_id and session_id in self._pending_address_by_session:
                del self._pending_address_by_session[session_id]
            return AgentResponse(
                success=False,
                message=f"抱歉，订单 {order_id} 当前状态为【{order['status']}】，已无法修改地址。",
                data={"order": order, "action": "change_address", "can_modify": False},
            )

        parsed = self._parse_new_address_from_user_text(content, extracted)
        if parsed:
            return self._apply_address_update(order_id, order, parsed, session_id)

        if session_id:
            self._pending_address_by_session[session_id] = order_id
        current_addr = self._format_address(order["receive_address"])
        return AgentResponse(
            success=True,
            message=f"订单 {order_id} 可以修改地址。\n\n"
            f"当前地址：{current_addr}\n\n"
            f"请在下一条消息中发送完整新地址：省 + 市 + 区/县 + 详细门牌 + 收货人姓名 + 手机号"
            f"（可写在同一行；若已分两条说，第二条无需再说「改地址」）。",
            data={"order": order, "action": "change_address", "need_info": "new_address"},
        )

    def _apply_address_update(
        self,
        order_id: str,
        order: Dict,
        new_addr: Dict[str, str],
        session_id: str,
    ) -> AgentResponse:
        if session_id and session_id in self._pending_address_by_session:
            del self._pending_address_by_session[session_id]

        ok, err = self._repo.update_receive_address(order_id, new_addr)
        if not ok:
            return AgentResponse(
                success=False,
                message=f"地址未能保存到数据库：{err}",
                data={"order": order, "action": "change_address", "new_address": new_addr},
            )
        order = self._repo.fetch_by_order_id(order_id) or order

        msg = (
            f"✅ 订单 {order_id} 收货地址已更新。\n\n"
            f"新地址：{self._format_address(order['receive_address'])}"
        )
        return AgentResponse(
            success=True,
            message=msg,
            data={"order": order, "action": "change_address_done", "new_address": new_addr},
        )

    @staticmethod
    def _strip_address_noise(text: str) -> str:
        t = text
        for kw in ["改地址", "换地址", "修改地址", "新地址", "收货地址", "改为", "换成", "详细地址", "地址改成"]:
            t = t.replace(kw, " ")
        t = re.sub(r"订单[号编号]?\s*\d{10,20}", "", t)
        return t.strip()

    def _parse_new_address_from_user_text(
        self, content: str, extracted: Dict[str, Any]
    ) -> Optional[Dict[str, str]]:
        work = self._strip_address_noise(content)
        phone = None
        m = re.search(r"(1[3-9]\d{9})", work)
        if m:
            phone = m.group(1)
        elif extracted.get("phone"):
            phone = str(extracted["phone"])
        if not phone:
            return None

        work_no_phone = work.replace(phone, " ").strip()
        name = ""
        nm = re.search(r"(?:收货人|收件人|姓名|联系人)[:：\s]*([\u4e00-\u9fa5·．.\s]{2,12})", content)
        if nm:
            name = re.sub(r"\s+", "", nm.group(1)).strip("·．.")
        if not name:
            nm2 = re.search(r"([\u4e00-\u9fa5]{2,4})\s*(?:手机|电话)?\s*" + re.escape(phone), content)
            if nm2:
                name = nm2.group(1)

        geo = re.search(
            r"(?P<province>[\u4e00-\u9fa5]+?(?:省|自治区))?"
            r"\s*(?P<city>[\u4e00-\u9fa5]+?市)\s*"
            r"(?P<district>[\u4e00-\u9fa5]+?(?:区|县))\s*"
            r"(?P<detail>.+?)(?=1[3-9]\d{9}|$)",
            work_no_phone,
        )
        if geo:
            province = (geo.group("province") or "").strip()
            city = geo.group("city").strip()
            district = geo.group("district").strip()
            detail = geo.group("detail").strip()
        else:
            geo2 = re.search(
                r"(?P<city>[\u4e00-\u9fa5]+市)\s*"
                r"(?P<district>[\u4e00-\u9fa5]+?(?:区|县))\s*"
                r"(?P<detail>.+?)(?=1[3-9]\d{9}|$)",
                work_no_phone,
            )
            if not geo2:
                return None
            province = ""
            city = geo2.group("city").strip()
            district = geo2.group("district").strip()
            detail = geo2.group("detail").strip()

        detail = re.sub(r"[，,;；\s]+$", "", detail)
        if len(detail) < 4:
            return None
        if not name:
            name = "收件人"
        return {
            "name": name,
            "phone": phone,
            "province": province,
            "city": city,
            "district": district,
            "detail": detail,
        }

    def _handle_cancel_order(self, order_id: Optional[str], content: str) -> AgentResponse:
        if not order_id:
            m = re.search(r"\b(\d{10,20})\b", content)
            if m:
                order_id = m.group(1)
        if not order_id:
            return AgentResponse(
                success=False,
                message="取消订单需要提供订单号，请提供您要取消的订单号。",
                data={"action": "cancel", "need_info": "order_id"},
            )
        order = self._get_order(order_id)
        if not order:
            return AgentResponse(
                success=False,
                message=f"未找到订单号 {order_id}，请确认是否正确。",
                data={"action": "cancel", "order_id": order_id},
            )
        if not order["can_cancel"]:
            return AgentResponse(
                success=False,
                message=f"抱歉，订单 {order_id} 当前状态为【{order['status']}】，已无法取消。",
                data={"order": order, "action": "cancel", "can_cancel": False},
            )
        ok, err = self._repo.update_cancelled(order_id)
        if not ok:
            return AgentResponse(
                success=False,
                message=f"无法在数据库中完成取消：{err}",
                data={"order": order, "action": "cancel"},
            )
        order = self._repo.fetch_by_order_id(order_id) or order
        return AgentResponse(
            success=True,
            message=f"✅ 订单 {order_id} 已成功取消！\n\n"
            f"商品：{order['product_name']} x{order['quantity']}\n"
            f"金额：¥{order['total_amount']:.2f}\n\n"
            f"退款将在 3-7 个工作日内原路退回您的支付账户。",
            data={"order": order, "action": "cancel"},
        )

    def _handle_list_orders(self) -> AgentResponse:
        orders = self._list_all_orders()
        msg = f"您共有 {len(orders)} 个订单：\n\n"
        for o in orders:
            msg += self._format_order_brief(o) + "\n---\n"
        return AgentResponse(success=True, message=msg, data={"orders": orders, "action": "list_all"})

    _STATUS_EMOJI = {"待发货": "📦", "已发货": "🚚", "已完成": "✅", "已取消": "❌"}

    def _format_order_info(self, o: Dict) -> str:
        emoji = self._STATUS_EMOJI.get(o["status"], "📋")
        info = (
            f"{emoji} 订单详情\n"
            f"{'━'*20}\n"
            f"📋 订单号：{o['order_id']}\n"
            f"📌 状态：{o['status']}\n"
            f"📅 下单时间：{o['create_time']}\n\n"
            f"🛒 商品：{o['product_name']} x{o['quantity']}  ¥{o['total_amount']:.2f}\n\n"
            f"📍 收货地址：{self._format_address(o['receive_address'])}"
        )
        if o.get("tracking_number"):
            info += f"\n🚚 物流单号：{o['tracking_number']}"
        actions = []
        if o.get("can_modify_address"):
            actions.append("可修改地址")
        if o.get("can_cancel"):
            actions.append("可取消订单")
        if actions:
            info += "\n💡 " + " | ".join(actions)
        return info

    def _format_order_brief(self, o: Dict) -> str:
        emoji = self._STATUS_EMOJI.get(o["status"], "📋")
        return (
            f"{emoji} {o['order_id']} | {o['status']}\n"
            f"   {o['product_name']} x{o['quantity']} | ¥{o['total_amount']:.2f}"
        )

    def _format_address(self, a: Dict) -> str:
        return f"{a['province']}{a['city']}{a['district']}{a['detail']} ({a['name']} {a['phone']})"
