import asyncio
import time
import re
from typing import Dict, Any, Optional
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain, At
import json
import os

@register("astrbot_plugin_entry_review", "Developer", "入群申请审核插件，自动转发入群申请到指定群聊进行审核", "1.0.0")
class EntryReviewPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.pending_requests: Dict[str, Dict[str, Any]] = {}  # 存储待审核的入群申请
        self.load_config()

    async def initialize(self):
        """插件初始化"""
        logger.info("入群申请审核插件已初始化")
        
        # 设置默认配置
        if not hasattr(self, 'config') or not self.config:
            self.config = {
                "source_group_id": "",  # 监听入群申请的群号
                "target_group_id": "",  # 转发审核消息的群号
                "authorized_users": [],  # 有权限审核的用户列表
                "auto_approve_timeout": 3600,  # 自动通过超时时间（秒）
                "enable_auto_approve": True,  # 是否启用自动通过
                "approval_message_template": "欢迎 {nickname} 加入群聊！",
                "rejection_message_template": "很抱歉，您的入群申请未通过审核。原因：{reason}"
            }
            self.save_config()

    def load_config(self):
        """加载配置"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = {
                    "source_group_id": "",
                    "target_group_id": "",
                    "authorized_users": [],
                    "auto_approve_timeout": 3600,
                    "enable_auto_approve": True,
                    "approval_message_template": "欢迎 {nickname} 加入群聊！",
                    "rejection_message_template": "很抱歉，您的入群申请未通过审核。原因：{reason}"
                }
                self.save_config()
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self.config = {
                "source_group_id": "",
                "target_group_id": "",
                "authorized_users": [],
                "auto_approve_timeout": 3600,
                "enable_auto_approve": True,
                "approval_message_template": "欢迎 {nickname} 加入群聊！",
                "rejection_message_template": "很抱歉，您的入群申请未通过审核。原因：{reason}"
            }

    def save_config(self):
        """保存配置"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    @filter.command("设置源群")
    async def set_source_group(self, event: AstrMessageEvent):
        """设置监听入群申请的源群"""
        try:
            parts = event.message_str.split()
            if len(parts) < 2:
                yield event.plain_result("请输入正确的格式：/设置源群 群号")
                return
                
            group_id = parts[1]
            self.config["source_group_id"] = group_id
            self.save_config()
            yield event.plain_result(f"已设置源群为：{group_id}")
        except Exception as e:
            logger.error(f"设置源群失败: {e}")
            yield event.plain_result(f"设置源群失败：{str(e)}")

    @filter.command("设置审核群")
    async def set_target_group(self, event: AstrMessageEvent):
        """设置转发审核消息的目标群"""
        try:
            parts = event.message_str.split()
            if len(parts) < 2:
                yield event.plain_result("请输入正确的格式：/设置审核群 群号")
                return
                
            group_id = parts[1]
            self.config["target_group_id"] = group_id
            self.save_config()
            yield event.plain_result(f"已设置审核群为：{group_id}")
        except Exception as e:
            logger.error(f"设置审核群失败: {e}")
            yield event.plain_result(f"设置审核群失败：{str(e)}")

    @filter.command("添加审核员")
    async def add_reviewer(self, event: AstrMessageEvent):
        """添加有权限审核的用户"""
        try:
            parts = event.message_str.split()
            if len(parts) < 2:
                yield event.plain_result("请输入正确的格式：/添加审核员 QQ号")
                return
                
            user_id = parts[1]
            authorized_users = self.config.get("authorized_users", [])
            if user_id not in authorized_users:
                authorized_users.append(user_id)
                self.config["authorized_users"] = authorized_users
                self.save_config()
                yield event.plain_result(f"已添加审核员：{user_id}")
            else:
                yield event.plain_result(f"用户 {user_id} 已经是审核员")
        except Exception as e:
            logger.error(f"添加审核员失败: {e}")
            yield event.plain_result(f"添加审核员失败：{str(e)}")

    @filter.command("查看配置")
    async def show_config(self, event: AstrMessageEvent):
        """查看当前配置"""
        config_text = f"""当前配置：
源群ID：{self.config.get('source_group_id', '未设置')}
审核群ID：{self.config.get('target_group_id', '未设置')}
审核员：{', '.join(self.config.get('authorized_users', []))}
自动通过超时：{self.config.get('auto_approve_timeout', 3600)}秒
启用自动通过：{self.config.get('enable_auto_approve', True)}"""
        yield event.plain_result(config_text)

    def _safe_format(self, template: str, **kwargs) -> str:
        """安全的字符串格式化，避免KeyError"""
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"模板格式化缺少参数: {e}")
            return template

    def _format_timestamp(self, timestamp: Optional[int] = None) -> str:
        """格式化时间戳"""
        if timestamp is None:
            timestamp = int(time.time())
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))

    @filter.event_message_type(filter.EventMessageType.OTHER_MESSAGE)
    async def handle_other_events(self, event: AstrMessageEvent):
        """处理其他类型的事件，包括入群申请"""
        try:
            # 检查是否是入群申请事件
            raw_message = getattr(event, 'raw_message', None)
            if raw_message and hasattr(raw_message, 'post_type'):
                if raw_message.post_type == 'request' and raw_message.request_type == 'group':
                    await self._process_group_request(event)
        except Exception as e:
            logger.error(f"处理其他事件失败: {e}")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def handle_group_message(self, event: AstrMessageEvent):
        """处理群消息事件"""
        try:
            # 检查是否是审核群的审核指令
            if event.get_group_id() == self.config.get("target_group_id"):
                await self._process_review_command(event)
        except Exception as e:
            logger.error(f"处理群消息失败: {e}")

    async def _process_group_request(self, event: AstrMessageEvent):
        """处理入群申请"""
        try:
            raw_message = event.raw_message
            user_id = str(raw_message.user_id)
            group_id = str(raw_message.group_id)
            comment = getattr(raw_message, 'comment', '无')
            flag = getattr(raw_message, 'flag', '')
            
            # 检查是否是配置的源群
            if group_id != self.config.get("source_group_id"):
                return
            
            # 获取申请者信息
            nickname = f"用户{user_id}"
            
            # 存储申请信息
            request_info = {
                'user_id': user_id,
                'group_id': group_id,
                'nickname': nickname,
                'comment': comment,
                'flag': flag,
                'timestamp': int(time.time()),
                'status': 'pending'
            }
            
            self.pending_requests[user_id] = request_info
            
            # 转发到审核群
            target_group_id = self.config.get("target_group_id")
            if target_group_id:
                review_message = f"""📝 新的入群申请
👤 申请人：{nickname} ({user_id})
🏠 申请群：{group_id}
💬 申请理由：{comment}
⏰ 申请时间：{self._format_timestamp()}

请审核员回复：
✅ /通过 {user_id}
❌ /拒绝 {user_id} [原因]"""
                
                await self.send_message_to_group(target_group_id, review_message)
                
                # 设置自动通过定时器
                if self.config.get("enable_auto_approve", True):
                    timeout = self.config.get("auto_approve_timeout", 3600)
                    asyncio.create_task(self._auto_approve_after_timeout(user_id, int(group_id), nickname, flag))
                    
            logger.info(f"处理入群申请：用户 {user_id} 申请加入群 {group_id}")
            
        except Exception as e:
            logger.error(f"处理入群申请失败: {e}")
            error_context = {
                'error': str(e),
                'event_type': type(event).__name__,
                'raw_message': str(getattr(event, 'raw_message', 'None'))
            }
            
            # 发送错误通知到审核群
            target_group_id = self.config.get("target_group_id")
            if target_group_id:
                error_message = f"⚠️ 处理入群申请时发生错误：{str(e)}"
                try:
                    await self.send_message_to_group(target_group_id, error_message)
                except Exception as send_error:
                    logger.error(f"发送错误通知失败: {send_error}")

    async def handle_group_request_simulation(self, user_id: str, group_id: str, comment: str = "无"):
        """模拟处理入群申请（用于测试）"""
        try:
            nickname = f"测试用户{user_id}"
            
            # 存储申请信息
            request_info = {
                'user_id': user_id,
                'group_id': group_id,
                'nickname': nickname,
                'comment': comment,
                'flag': f'test_flag_{user_id}',
                'timestamp': int(time.time()),
                'status': 'pending'
            }
            
            self.pending_requests[user_id] = request_info
            
            # 转发到审核群
            target_group_id = self.config.get("target_group_id")
            if target_group_id:
                review_message = f"""📝 新的入群申请（测试）
👤 申请人：{nickname} ({user_id})
🏠 申请群：{group_id}
💬 申请理由：{comment}
⏰ 申请时间：{self._format_timestamp()}

请审核员回复：
✅ /通过 {user_id}
❌ /拒绝 {user_id} [原因]"""
                
                await self.send_message_to_group(target_group_id, review_message)
                
                # 设置自动通过定时器
                if self.config.get("enable_auto_approve", True):
                    timeout = self.config.get("auto_approve_timeout", 3600)
                    asyncio.create_task(self._auto_approve_after_timeout(user_id, int(group_id), nickname, f'test_flag_{user_id}'))
                    
            logger.info(f"模拟处理入群申请：用户 {user_id} 申请加入群 {group_id}")
            
        except Exception as e:
            logger.error(f"模拟处理入群申请失败: {e}")

    async def send_message_to_group(self, group_id: str, message: str):
        """发送消息到指定群"""
        try:
            # 使用AstrBot的API发送群消息
            from astrbot.core.platform.astr_message_event import AstrBotMessage
            from astrbot.core.platform.message_type import MessageType
            from astrbot.core.message.message_event_result import MessageEventResult
            
            # 创建消息事件
            bot_message = AstrBotMessage()
            bot_message.type = MessageType.GROUP_MESSAGE
            bot_message.group_id = group_id
            bot_message.message_str = message
            
            # 通过平台适配器发送消息
            platform_adapter = self.context.get_platform_adapter()
            if platform_adapter:
                await platform_adapter.send_message(bot_message, message)
            else:
                logger.warning("无法获取平台适配器，消息发送失败")
                
        except Exception as e:
            logger.error(f"发送群消息失败: {e}")
            # 备用方案：尝试使用事件结果发送
            try:
                # 这里需要根据实际的AstrBot API调整
                pass
            except Exception as backup_error:
                logger.error(f"备用发送方案也失败: {backup_error}")

    @filter.command("测试申请")
    async def test_request(self, event):
        """测试入群申请功能"""
        try:
            parts = event.message_str.split()
            if len(parts) < 3:
                yield event.plain_result("请输入正确的格式：/测试申请 用户ID 群号 [申请理由]")
                return
                
            user_id = parts[1]
            group_id = parts[2]
            comment = " ".join(parts[3:]) if len(parts) > 3 else "测试申请"
            
            await self.handle_group_request_simulation(user_id, group_id, comment)
            yield event.plain_result(f"已模拟用户 {user_id} 申请加入群 {group_id}")
            
        except Exception as e:
            logger.error(f"测试申请失败: {e}")
            yield event.plain_result(f"测试申请失败：{str(e)}")

    async def _process_review_command(self, event: AstrMessageEvent):
        """处理审核指令"""
        try:
            message = event.message_str.strip()
            sender_id = str(event.get_sender_id())
            
            # 检查权限
            authorized_users = self.config.get("authorized_users", [])
            if sender_id not in authorized_users and not event.is_admin():
                return
            
            # 处理通过指令
            if message.startswith("/通过"):
                parts = message.split()
                if len(parts) >= 2:
                    user_id = parts[1]
                    await self._approve_request(event, user_id, sender_id)
                else:
                    yield event.plain_result("请输入正确的格式：/通过 用户ID")
            
            # 处理拒绝指令
            elif message.startswith("/拒绝"):
                parts = message.split()
                if len(parts) >= 2:
                    user_id = parts[1]
                    reason = " ".join(parts[2:]) if len(parts) > 2 else "未通过审核"
                    await self._reject_request(event, user_id, sender_id, reason)
                else:
                    yield event.plain_result("请输入正确的格式：/拒绝 用户ID [原因]")
            
            # 处理查询指令
            elif message == "/待审核":
                pending_list = []
                for user_id, info in self.pending_requests.items():
                    if info['status'] == 'pending':
                        pending_list.append(f"👤 {info['nickname']} ({user_id}) - {self._format_timestamp(info['timestamp'])}")
                
                if pending_list:
                    result = "📋 待审核申请列表：\n" + "\n".join(pending_list)
                else:
                    result = "✅ 当前没有待审核的申请"
                
                yield event.plain_result(result)
                
        except Exception as e:
            logger.error(f"处理审核指令失败: {e}")
            yield event.plain_result(f"处理审核指令失败：{str(e)}")

    async def _check_admin_permission(self, event: AstrMessageEvent, user_id: str, group_id: str) -> bool:
        """检查管理员权限"""
        try:
            # 这里需要根据实际的AstrBot API来检查群管理员权限
            # 暂时返回True，实际使用时需要实现具体的权限检查逻辑
            return True
        except Exception as e:
            logger.error(f"检查管理员权限失败: {e}")
            return False

    async def _approve_request(self, event: AstrMessageEvent, user_id: str, operator: str):
        """通过入群申请"""
        try:
            if user_id not in self.pending_requests:
                yield event.plain_result(f"❌ 未找到用户 {user_id} 的申请记录")
                return
            
            request_info = self.pending_requests[user_id]
            if request_info['status'] != 'pending':
                yield event.plain_result(f"❌ 用户 {user_id} 的申请已经被处理过了")
                return
            
            # 更新申请状态
            request_info['status'] = 'approved'
            request_info['operator'] = operator
            request_info['process_time'] = int(time.time())
            
            # 调用平台API通过申请
            try:
                platform_adapter = self.context.get_platform_adapter()
                if platform_adapter and hasattr(platform_adapter, 'set_group_add_request'):
                    await platform_adapter.set_group_add_request(
                        flag=request_info['flag'],
                        sub_type='add',
                        approve=True
                    )
                else:
                    logger.warning("平台适配器不支持处理入群申请")
            except Exception as api_error:
                logger.error(f"调用平台API失败: {api_error}")
            
            # 发送通知消息
            approval_message = self._safe_format(
                self.config.get("approval_message_template", "欢迎 {nickname} 加入群聊！"),
                nickname=request_info['nickname'],
                user_id=user_id
            )
            
            # 发送到源群
            source_group_id = self.config.get("source_group_id")
            if source_group_id:
                await self.send_message_to_group(source_group_id, approval_message)
            
            # 回复审核结果
            result_message = f"✅ 已通过用户 {request_info['nickname']} ({user_id}) 的入群申请"
            yield event.plain_result(result_message)
            
            # 清理申请记录
            await self._cleanup_request(user_id)
            
            logger.info(f"通过入群申请：用户 {user_id}，操作员 {operator}")
            
        except Exception as e:
            logger.error(f"通过入群申请失败: {e}")
            yield event.plain_result(f"❌ 处理申请失败：{str(e)}")

    async def _reject_request(self, event: AstrMessageEvent, user_id: str, operator: str, reason: str = ""):
        """拒绝入群申请"""
        try:
            if user_id not in self.pending_requests:
                yield event.plain_result(f"❌ 未找到用户 {user_id} 的申请记录")
                return
            
            request_info = self.pending_requests[user_id]
            if request_info['status'] != 'pending':
                yield event.plain_result(f"❌ 用户 {user_id} 的申请已经被处理过了")
                return
            
            # 更新申请状态
            request_info['status'] = 'rejected'
            request_info['operator'] = operator
            request_info['process_time'] = int(time.time())
            request_info['reject_reason'] = reason
            
            # 调用平台API拒绝申请
            try:
                platform_adapter = self.context.get_platform_adapter()
                if platform_adapter and hasattr(platform_adapter, 'set_group_add_request'):
                    await platform_adapter.set_group_add_request(
                        flag=request_info['flag'],
                        sub_type='add',
                        approve=False,
                        reason=reason
                    )
                else:
                    logger.warning("平台适配器不支持处理入群申请")
            except Exception as api_error:
                logger.error(f"调用平台API失败: {api_error}")
            
            # 发送拒绝通知（如果需要）
            rejection_message = self._safe_format(
                self.config.get("rejection_message_template", "很抱歉，您的入群申请未通过审核。原因：{reason}"),
                nickname=request_info['nickname'],
                user_id=user_id,
                reason=reason or "未通过审核"
            )
            
            # 回复审核结果
            result_message = f"❌ 已拒绝用户 {request_info['nickname']} ({user_id}) 的入群申请\n原因：{reason or '未通过审核'}"
            yield event.plain_result(result_message)
            
            # 清理申请记录
            await self._cleanup_request(user_id)
            
            logger.info(f"拒绝入群申请：用户 {user_id}，操作员 {operator}，原因 {reason}")
            
        except Exception as e:
            logger.error(f"拒绝入群申请失败: {e}")
            yield event.plain_result(f"❌ 处理申请失败：{str(e)}")

    async def _auto_approve_after_timeout(self, user_id: str, group_id: int, nickname: str, flag: str):
        """超时后自动通过申请"""
        try:
            timeout = self.config.get("auto_approve_timeout", 3600)
            await asyncio.sleep(timeout)
            
            # 检查申请是否还在待审核状态
            if user_id in self.pending_requests and self.pending_requests[user_id]['status'] == 'pending':
                request_info = self.pending_requests[user_id]
                
                # 更新申请状态
                request_info['status'] = 'auto_approved'
                request_info['operator'] = 'system'
                request_info['process_time'] = int(time.time())
                
                # 调用平台API通过申请
                try:
                    platform_adapter = self.context.get_platform_adapter()
                    if platform_adapter and hasattr(platform_adapter, 'set_group_add_request'):
                        await platform_adapter.set_group_add_request(
                            flag=flag,
                            sub_type='add',
                            approve=True
                        )
                    else:
                        logger.warning("平台适配器不支持处理入群申请")
                except Exception as api_error:
                    logger.error(f"自动通过时调用平台API失败: {api_error}")
                
                # 发送自动通过通知
                auto_approval_message = f"⏰ 系统自动通过：{nickname} ({user_id}) 的入群申请（超时自动通过）"
                
                # 发送到审核群
                target_group_id = self.config.get("target_group_id")
                if target_group_id:
                    await self.send_message_to_group(target_group_id, auto_approval_message)
                
                # 发送欢迎消息到源群
                source_group_id = self.config.get("source_group_id")
                if source_group_id:
                    welcome_message = self._safe_format(
                        self.config.get("approval_message_template", "欢迎 {nickname} 加入群聊！"),
                        nickname=nickname,
                        user_id=user_id
                    )
                    await self.send_message_to_group(source_group_id, welcome_message)
                
                # 清理申请记录
                await self._cleanup_request(user_id)
                
                logger.info(f"自动通过入群申请：用户 {user_id}")
                
        except Exception as e:
            logger.error(f"自动通过申请失败: {e}")

    async def _cleanup_request(self, user_id: str):
        """清理申请记录"""
        try:
            if user_id in self.pending_requests:
                # 可以选择删除记录或者保留一段时间用于审计
                # 这里选择保留24小时后删除
                request_info = self.pending_requests[user_id]
                
                async def delayed_cleanup():
                    await asyncio.sleep(24 * 3600)  # 24小时后删除
                    if user_id in self.pending_requests:
                        del self.pending_requests[user_id]
                        logger.debug(f"已清理用户 {user_id} 的申请记录")
                
                asyncio.create_task(delayed_cleanup())
                
        except Exception as e:
            logger.error(f"清理申请记录失败: {e}")

    # 兼容性方法
    async def approve_request(self, user_id: str, event: AstrMessageEvent):
        """兼容性方法：通过申请"""
        await self._approve_request(event, user_id, str(event.get_sender_id()))

    async def reject_request(self, user_id: str, event: AstrMessageEvent):
        """兼容性方法：拒绝申请"""
        await self._reject_request(event, user_id, str(event.get_sender_id()))

    @filter.command("帮助")
    async def help_command(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = """🤖 入群申请审核插件帮助

📋 配置指令：
/设置源群 <群号> - 设置监听入群申请的群
/设置审核群 <群号> - 设置转发审核消息的群
/添加审核员 <QQ号> - 添加审核员
/查看配置 - 查看当前配置

🔍 审核指令（仅审核群有效）：
/通过 <用户ID> - 通过入群申请
/拒绝 <用户ID> [原因] - 拒绝入群申请
/待审核 - 查看待审核申请列表

🧪 测试指令：
/测试申请 <用户ID> <群号> [申请理由] - 模拟入群申请

💡 说明：
- 插件会自动监听源群的入群申请
- 申请信息会转发到审核群
- 审核员可以在审核群中处理申请
- 支持超时自动通过功能

❓ 如需更多帮助，请联系管理员"""
        
        yield event.plain_result(help_text)

    async def terminate(self):
        """插件终止时的清理工作"""
        try:
            logger.info("入群申请审核插件正在终止...")
            # 清理待处理的申请
            self.pending_requests.clear()
            logger.info("入群申请审核插件已终止")
        except Exception as e:
            logger.error(f"插件终止时发生错误: {e}")
