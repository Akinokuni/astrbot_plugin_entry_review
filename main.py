import asyncio
import time
import re
from typing import Dict, Any, Optional
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import json
import os

@register("astrbot_plugin_entry_review_fixed", "Developer", "入群申请审核插件（修复版），自动转发入群申请到指定群聊进行审核", "1.1.0")
class EntryReviewPluginFixed(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        self.config = {}
        self.debug_mode = False
        self.debug_log_events = True
        self.debug_log_api_calls = True
    
    async def initialize(self):
        """初始化插件"""
        self.load_config()
        self._init_debug_mode()
        
        # 注册事件监听器 - 使用正确的事件类型
        try:
            # 尝试注册请求事件监听器
            # 获取第一个可用的平台适配器
            platform_adapter = None
            if self.context.platform_manager and self.context.platform_manager.platform_insts:
                platform_adapter = self.context.platform_manager.platform_insts[0]
            if platform_adapter and hasattr(platform_adapter, 'register_event_handler'):
                await platform_adapter.register_event_handler('request', self._handle_request_event)
                self._debug_log("已注册请求事件监听器", "INFO")
            else:
                self._debug_log("平台适配器不支持事件监听器注册，将使用消息监听方式", "WARNING")
        except Exception as e:
            self._debug_log(f"注册事件监听器失败: {e}", "ERROR")
        
        logger.info("入群申请审核插件（修复版）已初始化")
    
    def load_config(self):
        """加载配置"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                # 默认配置
                self.config = {
                    "source_group_id": "",
                    "target_group_id": "",
                    "reviewers": [],
                    "auto_approve_timeout": 300,
                    "debug_mode": True,
                    "debug_log_events": True,
                    "debug_log_api_calls": True,
                    "notification_template": {
                        "new_request": "🔔 新的入群申请\n\n👤 申请人: {nickname} ({user_id})\n🏠 申请群: {group_id}\n💬 申请理由: {comment}\n⏰ 申请时间: {timestamp}\n\n请使用以下指令进行审核:\n✅ /通过 {user_id}\n❌ /拒绝 {user_id} [理由]\n📋 /查看 {user_id}\n\n申请将在 {timeout} 秒后自动通过",
                        "approved": "✅ 入群申请已通过\n\n👤 申请人: {nickname} ({user_id})\n🏠 申请群: {group_id}\n👨‍💼 操作员: {operator}\n⏰ 处理时间: {timestamp}",
                        "rejected": "❌ 入群申请已拒绝\n\n👤 申请人: {nickname} ({user_id})\n🏠 申请群: {group_id}\n👨‍💼 操作员: {operator}\n📝 拒绝理由: {reason}\n⏰ 处理时间: {timestamp}",
                        "auto_approved": "⏰ 入群申请已自动通过\n\n👤 申请人: {nickname} ({user_id})\n🏠 申请群: {group_id}\n⏰ 处理时间: {timestamp}\n\n原因: 超时自动通过"
                    }
                }
                self.save_config()
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self.config = {}
    
    def _init_debug_mode(self):
        """初始化调试模式"""
        self.debug_mode = self.config.get("debug_mode", True)
        self.debug_log_events = self.config.get("debug_log_events", True)
        self.debug_log_api_calls = self.config.get("debug_log_api_calls", True)
        
        if self.debug_mode:
            logger.info("调试模式已启用")
            logger.info(f"事件日志: {self.debug_log_events}")
            logger.info(f"API调用日志: {self.debug_log_api_calls}")
    
    def _debug_log(self, message: str, level: str = "DEBUG"):
        """调试日志"""
        if self.debug_mode:
            if level == "INFO":
                logger.info(f"[入群审核] {message}")
            elif level == "WARNING":
                logger.warning(f"[入群审核] {message}")
            elif level == "ERROR":
                logger.error(f"[入群审核] {message}")
            else:
                logger.debug(f"[入群审核] {message}")
    
    def _debug_log_event(self, event_data: dict, action: str):
        """调试事件日志"""
        if self.debug_mode and self.debug_log_events:
            logger.debug(f"[入群审核-事件] {action}: {event_data}")
    
    def _debug_log_api_call(self, api_name: str, params: dict, result: Any = None, error: Exception = None):
        """调试API调用日志"""
        if self.debug_mode and self.debug_log_api_calls:
            if error:
                logger.error(f"[入群审核-API] {api_name} 失败: {error}, 参数: {params}")
            else:
                logger.debug(f"[入群审核-API] {api_name} 成功: 参数={params}, 结果={result}")
    
    def save_config(self):
        """保存配置"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
    
    async def _handle_request_event(self, event_data: dict):
        """处理请求事件（新的事件监听器）"""
        self._debug_log_event(event_data, "收到请求事件")
        
        try:
            if event_data.get('request_type') == 'group' and event_data.get('sub_type') == 'add':
                await self._process_group_request_new(event_data)
        except Exception as e:
            self._debug_log(f"处理请求事件失败: {e}", "ERROR")
    
    async def _process_group_request_new(self, event_data: dict):
        """处理新的入群申请事件"""
        try:
            user_id = str(event_data.get('user_id', ''))
            group_id = str(event_data.get('group_id', ''))
            comment = event_data.get('comment', '')
            flag = event_data.get('flag', '')
            
            self._debug_log(f"处理入群申请: user_id={user_id}, group_id={group_id}, flag={flag}")
            
            # 检查是否是需要审核的群
            source_group_id = self.config.get('source_group_id', '')
            if source_group_id and group_id != source_group_id:
                self._debug_log(f"群 {group_id} 不在审核范围内，跳过")
                return
            
            # 获取用户信息
            # 获取第一个可用的平台适配器
            platform_adapter = None
            if self.context.platform_manager and self.context.platform_manager.platform_insts:
                platform_adapter = self.context.platform_manager.platform_insts[0]
            user_info = None
            try:
                user_info = await platform_adapter.get_stranger_info(user_id=int(user_id))
            except Exception as e:
                self._debug_log(f"获取用户信息失败: {e}", "WARNING")
            
            nickname = user_info.get('nickname', f'用户{user_id}') if user_info else f'用户{user_id}'
            
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
            self._debug_log(f"已存储申请信息: {request_info}")
            
            # 发送通知到审核群
            target_group_id = self.config.get('target_group_id', '')
            if target_group_id:
                template = self.config.get('notification_template', {}).get('new_request', '')
                timeout = self.config.get('auto_approve_timeout', 300)
                
                message = self._safe_format(template,
                    nickname=nickname,
                    user_id=user_id,
                    group_id=group_id,
                    comment=comment or '无',
                    timestamp=self._format_timestamp(),
                    timeout=timeout
                )
                
                await self.send_message_to_group(target_group_id, message)
                self._debug_log(f"已发送通知到审核群 {target_group_id}")
                
                # 启动自动通过定时器
                if timeout > 0:
                    asyncio.create_task(self._auto_approve_after_timeout(
                        user_id, int(group_id), nickname, flag
                    ))
                    self._debug_log(f"已启动自动通过定时器，{timeout}秒后自动通过")
            
        except Exception as e:
            self._debug_log(f"处理入群申请失败: {e}", "ERROR")
    
    @filter.command("设置源群")
    async def set_source_group(self, event: AstrMessageEvent, group_id: str):
        """设置需要审核的源群"""
        try:
            self.config['source_group_id'] = group_id
            self.save_config()
            return MessageEventResult().message(f"✅ 已设置源群为: {group_id}")
        except Exception as e:
            logger.error(f"设置源群失败: {e}")
            return MessageEventResult().message(f"❌ 设置源群失败: {e}")
    
    @filter.command("设置审核群")
    async def set_target_group(self, event: AstrMessageEvent, group_id: str):
        """设置审核群"""
        try:
            self.config['target_group_id'] = group_id
            self.save_config()
            return MessageEventResult().message(f"✅ 已设置审核群为: {group_id}")
        except Exception as e:
            logger.error(f"设置审核群失败: {e}")
            return MessageEventResult().message(f"❌ 设置审核群失败: {e}")
    
    @filter.command("添加审核员")
    async def add_reviewer(self, event: AstrMessageEvent, user_id: str):
        """添加审核员"""
        try:
            reviewers = self.config.get('reviewers', [])
            if user_id not in reviewers:
                reviewers.append(user_id)
                self.config['reviewers'] = reviewers
                self.save_config()
                return MessageEventResult().message(f"✅ 已添加审核员: {user_id}")
            else:
                return MessageEventResult().message(f"ℹ️ 用户 {user_id} 已经是审核员")
        except Exception as e:
            logger.error(f"添加审核员失败: {e}")
            return MessageEventResult().message(f"❌ 添加审核员失败: {e}")
    
    @filter.command("查看配置")
    async def show_config(self, event: AstrMessageEvent):
        """查看当前配置"""
        try:
            config_text = f"📋 当前配置:\n\n"
            config_text += f"🏠 源群ID: {self.config.get('source_group_id', '未设置')}\n"
            config_text += f"🎯 审核群ID: {self.config.get('target_group_id', '未设置')}\n"
            config_text += f"👥 审核员: {', '.join(self.config.get('reviewers', []))}\n"
            config_text += f"⏰ 自动通过时间: {self.config.get('auto_approve_timeout', 300)}秒\n"
            config_text += f"🐛 调试模式: {'开启' if self.config.get('debug_mode', True) else '关闭'}\n"
            return MessageEventResult().message(config_text)
        except Exception as e:
            logger.error(f"查看配置失败: {e}")
            return MessageEventResult().message(f"❌ 查看配置失败: {e}")
    
    def _safe_format(self, template: str, **kwargs) -> str:
        """安全的字符串格式化"""
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError) as e:
            logger.warning(f"字符串格式化失败: {e}")
            return template
    
    def _format_timestamp(self, timestamp: Optional[int] = None) -> str:
        """格式化时间戳"""
        if timestamp is None:
            timestamp = int(time.time())
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
    
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def handle_group_request_events(self, event: AstrMessageEvent, *args, **kwargs):
        """处理群消息事件（备用方案）"""
        try:
            # 检查是否是审核群的消息
            target_group_id = self.config.get('target_group_id', '')
            if not target_group_id or str(event.message_obj.group_id) != target_group_id:
                return
            
            # 检查是否是审核指令
            message_text = event.message_str.strip()
            if message_text.startswith(('/通过', '/拒绝', '/查看')):
                return await self._process_review_command(event)
            
            # 检查是否是入群申请的原始事件数据（作为备用方案）
            raw_message = getattr(event, 'raw_message', {})
            if (raw_message.get('post_type') == 'request' and 
                raw_message.get('request_type') == 'group' and 
                raw_message.get('sub_type') == 'add'):
                
                await self._process_group_request_new(raw_message)
                
        except Exception as e:
            self._debug_log(f"处理群消息事件失败: {e}", "ERROR")
    
    async def send_message_to_group(self, group_id: str, message: str):
        """发送消息到群"""
        try:
            # 获取第一个可用的平台适配器
            platform_adapter = None
            if self.context.platform_manager and self.context.platform_manager.platform_insts:
                platform_adapter = self.context.platform_manager.platform_insts[0]
            result = await platform_adapter.send_group_msg(
                group_id=int(group_id),
                message=message
            )
            self._debug_log_api_call("send_group_msg", 
                {"group_id": group_id, "message": message}, 
                result
            )
            return result
        except Exception as e:
            self._debug_log_api_call("send_group_msg", 
                {"group_id": group_id, "message": message}, 
                error=e
            )
            logger.error(f"发送群消息失败: {e}")
            raise
    
    @filter.command("测试申请")
    async def test_group_request(self, event: AstrMessageEvent, user_id: str = "123456789", group_id: str = "987654321", comment: str = "测试申请"):
        """测试入群申请功能"""
        try:
            test_event = {
                'request_type': 'group',
                'sub_type': 'add',
                'user_id': int(user_id),
                'group_id': int(group_id),
                'comment': comment,
                'flag': f'test_flag_{int(time.time())}'
            }
            
            await self._process_group_request_new(test_event)
            return MessageEventResult().message(f"✅ 已发送测试申请: user_id={user_id}, group_id={group_id}")
        except Exception as e:
            logger.error(f"测试申请失败: {e}")
            return MessageEventResult().message(f"❌ 测试申请失败: {e}")
    
    async def _process_review_command(self, event: AstrMessageEvent, context=None):
        """处理审核指令"""
        try:
            message_text = event.message_str.strip()
            operator = str(event.message_obj.sender.user_id)
            
            # 检查是否是审核员
            reviewers = self.config.get('reviewers', [])
            if reviewers and operator not in reviewers:
                return MessageEventResult().message("❌ 您没有审核权限")
            
            if message_text.startswith('/通过'):
                parts = message_text.split(' ', 1)
                if len(parts) >= 2:
                    user_id = parts[1].strip()
                    return await self._approve_request(event, user_id, operator, context)
                else:
                    return MessageEventResult().message("❌ 请指定用户ID: /通过 <用户ID>")
            
            elif message_text.startswith('/拒绝'):
                parts = message_text.split(' ', 2)
                if len(parts) >= 2:
                    user_id = parts[1].strip()
                    reason = parts[2].strip() if len(parts) >= 3 else "申请被拒绝"
                    return await self._reject_request(event, user_id, operator, reason, context)
                else:
                    return MessageEventResult().message("❌ 请指定用户ID: /拒绝 <用户ID> [理由]")
            
            elif message_text.startswith('/查看'):
                parts = message_text.split(' ', 1)
                if len(parts) >= 2:
                    user_id = parts[1].strip()
                    return await self._show_request_info(event, user_id)
                else:
                    return MessageEventResult().message("❌ 请指定用户ID: /查看 <用户ID>")
                    
        except Exception as e:
            logger.error(f"处理审核指令失败: {e}")
            return MessageEventResult().message(f"❌ 处理指令失败: {e}")
    
    async def _approve_request(self, event: AstrMessageEvent, user_id: str, operator: str, context=None):
        """通过申请"""
        try:
            if user_id not in self.pending_requests:
                return MessageEventResult().message(f"❌ 未找到用户 {user_id} 的申请")
            
            request_info = self.pending_requests[user_id]
            
            # 调用API通过申请
            success = await self._call_set_group_add_request(request_info, approve=True)
            
            if success:
                # 更新状态
                request_info['status'] = 'approved'
                request_info['operator'] = operator
                request_info['processed_time'] = int(time.time())
                
                # 发送通知
                template = self.config.get('notification_template', {}).get('approved', '')
                message = self._safe_format(template,
                    nickname=request_info['nickname'],
                    user_id=user_id,
                    group_id=request_info['group_id'],
                    operator=operator,
                    timestamp=self._format_timestamp()
                )
                
                # 清理申请
                await self._cleanup_request(user_id)
                
                return MessageEventResult().message(message)
            else:
                return MessageEventResult().message(f"❌ 通过申请失败，请检查日志")
                
        except Exception as e:
            logger.error(f"通过申请失败: {e}")
            return MessageEventResult().message(f"❌ 通过申请失败: {e}")
    
    async def _reject_request(self, event: AstrMessageEvent, user_id: str, operator: str, reason: str = "", context=None):
        """拒绝申请"""
        try:
            if user_id not in self.pending_requests:
                return MessageEventResult().message(f"❌ 未找到用户 {user_id} 的申请")
            
            request_info = self.pending_requests[user_id]
            
            # 调用API拒绝申请
            success = await self._call_set_group_add_request(request_info, approve=False, reason=reason)
            
            if success:
                # 更新状态
                request_info['status'] = 'rejected'
                request_info['operator'] = operator
                request_info['reject_reason'] = reason
                request_info['processed_time'] = int(time.time())
                
                # 发送通知
                template = self.config.get('notification_template', {}).get('rejected', '')
                message = self._safe_format(template,
                    nickname=request_info['nickname'],
                    user_id=user_id,
                    group_id=request_info['group_id'],
                    operator=operator,
                    reason=reason or '无',
                    timestamp=self._format_timestamp()
                )
                
                # 清理申请
                await self._cleanup_request(user_id)
                
                return MessageEventResult().message(message)
            else:
                return MessageEventResult().message(f"❌ 拒绝申请失败，请检查日志")
                
        except Exception as e:
            logger.error(f"拒绝申请失败: {e}")
            return MessageEventResult().message(f"❌ 拒绝申请失败: {e}")
    
    async def _call_set_group_add_request(self, request_info: dict, approve: bool, reason: str = "") -> bool:
        """调用设置群添加请求API - 尝试多种方式"""
        # 获取第一个可用的平台适配器
        platform_adapter = None
        if self.context.platform_manager and self.context.platform_manager.platform_insts:
            platform_adapter = self.context.platform_manager.platform_insts[0]
        flag = request_info.get('flag', '')
        user_id = int(request_info['user_id'])
        group_id = int(request_info['group_id'])
        
        # 尝试多种API调用方式
        api_attempts = [
            # 方式1: 使用原始flag
            {
                'flag': flag,
                'approve': approve,
                'reason': reason
            },
            # 方式2: 使用user_id作为flag
            {
                'flag': str(user_id),
                'approve': approve,
                'reason': reason
            },
            # 方式3: 使用group_id_user_id格式
            {
                'flag': f"{group_id}_{user_id}",
                'approve': approve,
                'reason': reason
            },
            # 方式4: 添加sub_type参数
            {
                'flag': flag,
                'sub_type': 'add',
                'approve': approve,
                'reason': reason
            },
            # 方式5: 完整参数
            {
                'flag': flag,
                'sub_type': 'add',
                'type': 'group',
                'approve': approve,
                'reason': reason
            }
        ]
        
        for i, params in enumerate(api_attempts, 1):
            try:
                self._debug_log(f"尝试API调用方式 {i}: {params}")
                
                result = await platform_adapter.set_group_add_request(**params)
                
                self._debug_log_api_call(f"set_group_add_request_attempt_{i}", params, result)
                
                if result is not None:
                    self._debug_log(f"API调用方式 {i} 成功")
                    return True
                    
            except Exception as e:
                self._debug_log_api_call(f"set_group_add_request_attempt_{i}", params, error=e)
                self._debug_log(f"API调用方式 {i} 失败: {e}", "WARNING")
                continue
        
        # 所有方式都失败
        self._debug_log("所有API调用方式都失败", "ERROR")
        return False
    
    async def _show_request_info(self, event: AstrMessageEvent, user_id: str):
        """显示申请信息"""
        try:
            if user_id not in self.pending_requests:
                return MessageEventResult().message(f"❌ 未找到用户 {user_id} 的申请")
            
            request_info = self.pending_requests[user_id]
            
            info_text = f"📋 申请信息\n\n"
            info_text += f"👤 申请人: {request_info['nickname']} ({user_id})\n"
            info_text += f"🏠 申请群: {request_info['group_id']}\n"
            info_text += f"💬 申请理由: {request_info.get('comment', '无')}\n"
            info_text += f"🏷️ Flag: {request_info.get('flag', '无')}\n"
            info_text += f"📅 申请时间: {self._format_timestamp(request_info['timestamp'])}\n"
            info_text += f"📊 状态: {request_info['status']}\n"
            
            return MessageEventResult().message(info_text)
            
        except Exception as e:
            logger.error(f"显示申请信息失败: {e}")
            return MessageEventResult().message(f"❌ 显示申请信息失败: {e}")
    
    async def _auto_approve_after_timeout(self, user_id: str, group_id: int, nickname: str, flag: str):
        """超时后自动通过申请"""
        try:
            timeout = self.config.get('auto_approve_timeout', 300)
            await asyncio.sleep(timeout)
            
            # 检查申请是否还在待处理状态
            if user_id in self.pending_requests and self.pending_requests[user_id]['status'] == 'pending':
                request_info = self.pending_requests[user_id]
                
                # 自动通过申请
                success = await self._call_set_group_add_request(request_info, approve=True, reason="超时自动通过")
                
                if success:
                    # 更新状态
                    request_info['status'] = 'auto_approved'
                    request_info['processed_time'] = int(time.time())
                    
                    # 发送通知
                    template = self.config.get('notification_template', {}).get('auto_approved', '')
                    message = self._safe_format(template,
                        nickname=nickname,
                        user_id=user_id,
                        group_id=group_id,
                        timestamp=self._format_timestamp()
                    )
                    
                    target_group_id = self.config.get('target_group_id', '')
                    if target_group_id:
                        await self.send_message_to_group(target_group_id, message)
                    
                    # 清理申请
                    await self._cleanup_request(user_id)
                    
                    self._debug_log(f"用户 {user_id} 的申请已自动通过")
                else:
                    self._debug_log(f"用户 {user_id} 的申请自动通过失败", "ERROR")
                    
        except asyncio.CancelledError:
            self._debug_log(f"用户 {user_id} 的自动通过定时器被取消")
        except Exception as e:
            self._debug_log(f"自动通过申请失败: {e}", "ERROR")
    
    async def _cleanup_request(self, user_id: str):
        """清理申请记录"""
        try:
            if user_id in self.pending_requests:
                del self.pending_requests[user_id]
                self._debug_log(f"已清理用户 {user_id} 的申请记录")
        except Exception as e:
            self._debug_log(f"清理申请记录失败: {e}", "ERROR")
    
    @filter.command("帮助")
    async def help_command(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = """🤖 入群申请审核插件帮助

📋 配置指令:
• /设置源群 <群号> - 设置需要审核的群
• /设置审核群 <群号> - 设置审核消息发送的群
• /添加审核员 <用户ID> - 添加审核员
• /查看配置 - 查看当前配置

🔍 审核指令:
• /通过 <用户ID> - 通过入群申请
• /拒绝 <用户ID> [理由] - 拒绝入群申请
• /查看 <用户ID> - 查看申请详情

🧪 测试指令:
• /测试申请 [用户ID] [群号] [理由] - 发送测试申请

💡 说明:
- 申请会在设定时间后自动通过
- 支持多种flag格式以解决NapCatQQ兼容性问题
- 调试模式下会输出详细日志"""
        
        return MessageEventResult().message(help_text)
    
    async def terminate(self):
        """插件终止时的清理工作"""
        try:
            self._debug_log("插件正在终止...")
            # 这里可以添加清理逻辑
            logger.info("入群申请审核插件已终止")
        except Exception as e:
            logger.error(f"插件终止时发生错误: {e}")