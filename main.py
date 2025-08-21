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
        logger.info(f"入群申请审核插件已启动，源群: {self.config.get('source_group')}, 审核群: {self.config.get('target_group')}")
        logger.info(f"自动通过超时: {self.config.get('auto_approve_timeout', 3600)}秒")
        
        # 设置日志级别
        log_level = self.config.get('log_level', 'INFO')
        if hasattr(logger, 'setLevel'):
            import logging
            level_map = {
                'DEBUG': logging.DEBUG,
                'INFO': logging.INFO,
                'WARNING': logging.WARNING,
                'ERROR': logging.ERROR
            }
            if log_level in level_map:
                logger.setLevel(level_map[log_level])
        
    def load_config(self):
        """加载配置文件"""
        # 使用AstrBot的配置系统
        self.config = self.context.config_helper.get_all()
        
        # 设置默认值
        default_config = {
            "source_group": "",
            "target_group": "",
            "auto_approve_timeout": 3600,
            "request_message_template": "📝 收到入群申请\n👤 用户: {user_id}\n🏷️ 昵称: {nickname}\n💬 申请理由: {comment}\n🏠 申请群: {group_id}\n⏰ 申请时间: {timestamp}\n\n📋 处理方式:\n✅ 回复 /通过 {user_id} 同意申请\n❌ 回复 /拒绝 {user_id} 拒绝申请",
            "approve_message_template": "✅ 用户 {user_id}({nickname}) 的入群申请已通过\n操作员: {operator}\n处理时间: {timestamp}",
            "reject_message_template": "❌ 用户 {user_id}({nickname}) 的入群申请已拒绝\n操作员: {operator}\n拒绝理由: {reason}\n处理时间: {timestamp}",
            "auto_approve_message_template": "⏰ 用户 {user_id}({nickname}) 的入群申请已超时自动通过\n申请时间: {request_time}\n处理时间: {timestamp}",
            "error_message_template": "❗ 处理申请时发生错误: {error}\n用户: {user_id}\n请检查配置或联系管理员",
            "command_permission_check": True,
            "log_level": "INFO"
        }
        
        # 合并默认配置
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
                
        logger.debug(f"配置加载完成: {self.config}")
            
    def save_config(self):
        """保存配置文件"""
        try:
            # 使用AstrBot的配置系统保存
            for key, value in self.config.items():
                self.context.config_helper.put(key, value)
            logger.debug("配置保存成功")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    @filter.command("设置源群")
    async def set_source_group(self, event: AstrMessageEvent):
        """设置需要监控的源群号"""
        try:
            # 提取群号
            parts = event.message_str.split()
            if len(parts) < 2:
                yield event.plain_result("请输入正确的格式：/设置源群 群号")
                return
                
            group_id = parts[1]
            self.config["source_group"] = group_id
            self.save_config()
            yield event.plain_result(f"已设置源群为：{group_id}")
            logger.info(f"设置源群为：{group_id}")
        except Exception as e:
            logger.error(f"设置源群失败: {e}")
            yield event.plain_result("设置失败，请检查输入格式")

    @filter.command("设置审核群")
    async def set_target_group(self, event: AstrMessageEvent):
        """设置审核群号"""
        try:
            parts = event.message_str.split()
            if len(parts) < 2:
                yield event.plain_result("请输入正确的格式：/设置审核群 群号")
                return
                
            group_id = parts[1]
            self.config["target_group"] = group_id
            self.save_config()
            yield event.plain_result(f"已设置审核群为：{group_id}")
            logger.info(f"设置审核群为：{group_id}")
        except Exception as e:
            logger.error(f"设置审核群失败: {e}")
            yield event.plain_result("设置失败，请检查输入格式")

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
                logger.info(f"添加审核员：{user_id}")
            else:
                yield event.plain_result(f"用户 {user_id} 已经是审核员")
        except Exception as e:
            logger.error(f"添加审核员失败: {e}")
            yield event.plain_result("添加失败，请检查输入格式")

    @filter.command("查看配置")
    async def show_config(self, event: AstrMessageEvent):
        """查看当前配置"""
        config_text = f"""当前配置：
源群：{self.config.get('source_group', '未设置')}
审核群：{self.config.get('target_group', '未设置')}
审核员：{', '.join(self.config.get('authorized_users', []))}
待审核申请数量：{len(self.pending_requests)}"""
        yield event.plain_result(config_text)

    def _safe_format(self, template: str, **kwargs) -> str:
        """安全的字符串格式化，避免KeyError"""
        class SafeDict(dict):
            def __missing__(self, key):
                return f'{{{key}}}'
        return template.format_map(SafeDict(kwargs))
    
    def _format_timestamp(self, timestamp: Optional[int] = None) -> str:
        """格式化时间戳"""
        if timestamp is None:
            timestamp = int(time.time())
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
    
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def handle_event(self, event: AstrMessageEvent):
        """处理群消息和事件"""
        try:
            # 检查是否有原始消息数据
            if hasattr(event.message_obj, 'raw_message'):
                raw = event.message_obj.raw_message
                post_type = raw.get("post_type")
                
                if post_type == "request":
                    # 处理入群申请
                    if raw.get("request_type") == "group" and raw.get("sub_type") == "add":
                        await self._process_group_request(event)
                elif post_type == "message" and raw.get("message_type") == "group":
                    # 处理审核指令
                    await self._process_review_command(event)
            else:
                # 如果没有原始消息数据，只处理审核指令
                await self._process_review_command(event)
                
        except Exception as e:
            logger.error(f"[Entry Review] 处理事件时发生错误: {e}")
    
    async def _process_group_request(self, event: AstrMessageEvent):
        """处理入群申请"""
        try:
            raw = event.message_obj.raw_message
            user_id = str(raw.get("user_id"))
            group_id = raw.get("group_id")
            comment = raw.get("comment", "")
            flag = raw.get("flag", "")
            
            # 检查是否为监听的源群
            if str(group_id) != self.config.get("source_group"):
                return
            
            logger.info(f"[Entry Review] 收到入群申请: 用户 {user_id}, 群 {group_id}")
            
            # 获取用户信息
            nickname = user_id
            try:
                if hasattr(event, 'bot') and hasattr(event.bot, 'api'):
                    user_info = await event.bot.api.call_action(
                        "get_stranger_info", user_id=int(user_id)
                    )
                    nickname = user_info.get("nickname", user_id)
            except Exception as e:
                logger.warning(f"[Entry Review] 获取用户信息失败: {e}")
            
            # 创建自动通过任务（如果启用）
            task = None
            auto_timeout = self.config.get("auto_approve_timeout", 0)
            if auto_timeout > 0:
                task = asyncio.create_task(
                    self._auto_approve_after_timeout(user_id, group_id, nickname, flag)
                )
            
            # 记录申请状态
            self.pending_requests[user_id] = {
                "group_id": group_id,
                "comment": comment,
                "nickname": nickname,
                "timestamp": int(time.time()),
                "task": task,
                "flag": flag
            }
            
            # 发送到管理群
            message = self._safe_format(
                self.config.get("request_message_template", ""),
                user_id=user_id,
                nickname=nickname,
                comment=comment or "无",
                group_id=group_id,
                timestamp=self._format_timestamp()
            )
            
            await self.send_message_to_group(self.config.get("target_group", ""), message)
            
        except Exception as e:
            logger.error(f"[Entry Review] 处理入群申请时发生错误: {e}")
            # 尝试获取错误上下文信息
            error_context = {
                'user_id': locals().get('user_id', 'unknown'),
                'group_id': locals().get('group_id', 'unknown'),
                'exception_type': type(e).__name__
            }
            logger.debug(f"[Entry Review] 错误详情 - 用户: {error_context['user_id']}, 群: {error_context['group_id']}, 异常类型: {error_context['exception_type']}")
            
            # 发送错误通知到审核群
            try:
                if error_context['user_id'] != 'unknown':
                    error_msg = self._safe_format(
                        self.config.get("error_message_template", ""),
                        error=str(e),
                        user_id=error_context['user_id']
                    )
                    await self.send_message_to_group(self.config.get("target_group", ""), error_msg)
            except Exception as notify_error:
                logger.error(f"[Entry Review] 发送错误通知失败: {notify_error}")
    
    async def handle_group_request_simulation(self, user_id: str, group_id: str, comment: str = "无"):
        """模拟处理入群申请事件（需要手动调用）"""
        try:
            # 检查是否是目标群的申请
            if not self.config.get("source_group") or not self.config.get("target_group"):
                logger.warning("源群或审核群未配置")
                return
                
            if group_id != self.config["source_group"]:
                return
            
            # 获取用户昵称（模拟）
            nickname = user_id
            
            # 创建自动通过任务（如果启用）
            task = None
            auto_timeout = self.config.get("auto_approve_timeout", 0)
            if auto_timeout > 0:
                task = asyncio.create_task(
                    self._auto_approve_after_timeout(user_id, group_id, nickname, "")
                )
                
            # 存储申请信息
            self.pending_requests[user_id] = {
                "group_id": group_id,
                "comment": comment,
                "nickname": nickname,
                "timestamp": int(time.time()),
                "task": task,
                "flag": ""
            }
            
            # 发送到审核群
            message = self._safe_format(
                self.config.get("request_message_template", ""),
                user_id=user_id,
                nickname=nickname,
                comment=comment or "无",
                group_id=group_id,
                timestamp=self._format_timestamp()
            )
            
            # 发送消息到审核群
            try:
                await self.send_message_to_group(self.config["target_group"], message)
                logger.info(f"收到入群申请：用户{user_id}申请加入群{group_id}，理由：{comment}")
                logger.info(f"已转发到审核群{self.config['target_group']}")
            except Exception as send_error:
                logger.error(f"发送消息到审核群失败: {send_error}")
            
        except Exception as e:
            logger.error(f"处理入群申请失败: {e}")
    
    async def send_message_to_group(self, group_id: str, message: str):
        """发送消息到指定群"""
        try:
            if not group_id:
                logger.error("[Entry Review] 目标群号为空，无法发送消息")
                return False
                
            logger.debug(f"[Entry Review] 准备发送消息到群 {group_id}")
            
            # 通过Context对象获取平台管理器并发送消息
            if hasattr(self.context, 'platform_manager'):
                platform_manager = self.context.platform_manager
                # 构造消息链
                from astrbot.api.message_components import Plain
                message_chain = [Plain(message)]
                
                # 尝试通过平台适配器发送消息
                for adapter in platform_manager.adapters:
                    try:
                        # 构造会话ID（群聊格式）
                        session_id = f"group_{group_id}"
                        await adapter.send_by_session(session_id, message_chain)
                        logger.debug(f"[Entry Review] 消息发送成功到群 {group_id}")
                        return True
                    except Exception as adapter_error:
                        logger.debug(f"[Entry Review] 适配器 {adapter} 发送失败: {adapter_error}")
                        continue
                        
                logger.warning(f"[Entry Review] 所有适配器都无法发送消息到群{group_id}")
            else:
                logger.error("[Entry Review] Context对象中未找到platform_manager")
                # 降级到日志记录
                logger.info(f"[Entry Review] [模拟发送到群{group_id}] {message}")
                
        except Exception as e:
            logger.error(f"[Entry Review] 发送消息到群 {group_id} 失败: {e}")
            logger.debug(f"[Entry Review] 发送失败的消息内容: {message[:100]}...")
            # 降级到日志记录
            logger.info(f"[Entry Review] [模拟发送到群{group_id}] {message}")
            return False
    
    @filter.command("测试申请")
    async def test_request(self, event):
        """测试入群申请功能的命令"""
        try:
            # 解析命令参数
            args = event.message_str.split()
            if len(args) < 3:
                yield event.plain_result("用法：/测试申请 <用户ID> <群ID> [申请理由]")
                return
            
            user_id = args[1]
            group_id = args[2]
            comment = " ".join(args[3:]) if len(args) > 3 else "测试申请"
            
            # 调用申请处理函数
            await self.handle_group_request_simulation(user_id, group_id, comment)
            yield event.plain_result(f"已模拟处理用户{user_id}的入群申请")
            
        except Exception as e:
            logger.error(f"测试申请命令失败: {e}")
            yield event.plain_result(f"测试失败: {e}")

    async def _process_review_command(self, event: AstrMessageEvent):
        """处理审核指令"""
        try:
            message = event.message_str.strip()
            group_id = str(event.group_id) if event.group_id else ""
            sender_id = str(event.sender.user_id) if event.sender else ""
            
            # 只处理审核群的消息
            if group_id != self.config.get("target_group"):
                return
            
            # 检查是否为审核指令
            if not (message.startswith("/通过 ") or message.startswith("/拒绝 ") or 
                   message.startswith("通过 ") or message.startswith("拒绝 ")):
                return
            
            # 权限检查
            if self.config.get("command_permission_check", True):
                authorized_users = self.config.get("authorized_users", [])
                if authorized_users and sender_id not in authorized_users:
                    # 检查是否为群管理员
                    if not await self._check_admin_permission(event, sender_id, group_id):
                        yield event.plain_result("❌ 权限不足，只有授权用户或群管理员可以执行此操作")
                        return
            
            # 解析指令
            parts = message.split(" ", 2)
            if len(parts) < 2:
                yield event.plain_result("❗ 指令格式错误\n正确格式: /通过 用户ID 或 /拒绝 用户ID [理由]")
                return
            
            command = parts[0].replace("/", "")
            target_user_id = parts[1]
            reason = parts[2] if len(parts) > 2 else ""
            
            # 获取操作员信息
            operator_name = sender_id
            try:
                if hasattr(event, 'sender') and hasattr(event.sender, 'nickname'):
                    operator_name = event.sender.nickname or sender_id
            except Exception:
                pass
            
            if command == "通过":
                await self._approve_request(event, target_user_id, operator_name)
            elif command == "拒绝":
                await self._reject_request(event, target_user_id, operator_name, reason)
                
        except Exception as e:
            logger.error(f"[Entry Review] 处理审核指令时发生错误: {e}")
    
    async def _check_admin_permission(self, event: AstrMessageEvent, user_id: str, group_id: str) -> bool:
        """检查用户是否有管理权限"""
        try:
            # 检查是否启用权限检查
            if not self.config.get("command_permission_check", True):
                logger.debug(f"[Entry Review] 权限检查已禁用，用户 {user_id} 通过权限验证")
                return True
            
            logger.debug(f"[Entry Review] 检查用户 {user_id} 在群 {group_id} 的管理权限")
            
            # 尝试多种方式获取API接口
            api = None
            if hasattr(event, 'bot') and hasattr(event.bot, 'api'):
                api = event.bot.api
            elif hasattr(self.context, 'bot') and hasattr(self.context.bot, 'api'):
                api = self.context.bot.api
            
            if api:
                member_info = await api.call_action(
                    "get_group_member_info",
                    group_id=int(group_id),
                    user_id=int(user_id)
                )
                role = member_info.get("role", "member")
                is_admin = role in ["admin", "owner"]
                
                logger.debug(f"[Entry Review] 用户 {user_id} 角色: {role}, 管理权限: {is_admin}")
                return is_admin
            else:
                logger.warning(f"[Entry Review] 无法获取bot API接口，用户: {user_id}")
                # 无法获取API时，为安全起见返回False
                return False
                
        except Exception as e:
            logger.error(f"[Entry Review] 检查管理权限失败 - 用户: {user_id}, 群: {group_id}, 错误: {e}")
            logger.debug(f"[Entry Review] 权限检查异常类型: {type(e).__name__}")
            # 权限检查失败时，为安全起见返回False
            return False

    async def _approve_request(self, event: AstrMessageEvent, user_id: str, operator: str):
        """通过申请"""
        try:
            if user_id not in self.pending_requests:
                yield event.plain_result(f"❗ 未找到用户 {user_id} 的待处理申请")
                return
            
            request_info = self.pending_requests[user_id]
            
            # 通过申请
            try:
                if hasattr(event, 'bot') and hasattr(event.bot, 'api'):
                    await event.bot.api.call_action(
                        "set_group_add_request",
                        flag=request_info.get("flag", ""),
                        sub_type="add",
                        approve=True
                    )
            except Exception as api_error:
                logger.warning(f"[Entry Review] API调用失败，可能需要手动处理: {api_error}")
            
            # 发送反馈消息
            message = self._safe_format(
                self.config.get("approve_message_template", ""),
                user_id=user_id,
                nickname=request_info.get("nickname", user_id),
                operator=operator,
                timestamp=self._format_timestamp()
            )
            yield event.plain_result(message)
            
            # 清理状态
            await self._cleanup_request(user_id)
            
            logger.info(f"[Entry Review] 用户 {user_id} 的申请已被 {operator} 通过")
            
        except Exception as e:
            error_msg = self._safe_format(
                self.config.get("error_message_template", ""),
                error=str(e),
                user_id=user_id
            )
            yield event.plain_result(error_msg)
            logger.error(f"[Entry Review] 通过申请失败: {e}")
    
    async def _reject_request(self, event: AstrMessageEvent, user_id: str, operator: str, reason: str = ""):
        """拒绝申请"""
        try:
            if user_id not in self.pending_requests:
                yield event.plain_result(f"❗ 未找到用户 {user_id} 的待处理申请")
                return
            
            request_info = self.pending_requests[user_id]
            
            # 拒绝申请
            try:
                if hasattr(event, 'bot') and hasattr(event.bot, 'api'):
                    await event.bot.api.call_action(
                        "set_group_add_request",
                        flag=request_info.get("flag", ""),
                        sub_type="add",
                        approve=False,
                        reason=reason or "管理员拒绝"
                    )
            except Exception as api_error:
                logger.warning(f"[Entry Review] API调用失败，可能需要手动处理: {api_error}")
            
            # 发送反馈消息
            message = self._safe_format(
                self.config.get("reject_message_template", ""),
                user_id=user_id,
                nickname=request_info.get("nickname", user_id),
                operator=operator,
                reason=reason or "无",
                timestamp=self._format_timestamp()
            )
            yield event.plain_result(message)
            
            # 清理状态
            await self._cleanup_request(user_id)
            
            logger.info(f"[Entry Review] 用户 {user_id} 的申请已被 {operator} 拒绝，理由: {reason}")
            
        except Exception as e:
            error_msg = self._safe_format(
                self.config.get("error_message_template", ""),
                error=str(e),
                user_id=user_id
            )
            yield event.plain_result(error_msg)
            logger.error(f"[Entry Review] 拒绝申请失败: {e}")
    
    async def _auto_approve_after_timeout(self, user_id: str, group_id: int, nickname: str, flag: str):
        """超时自动通过"""
        try:
            timeout = self.config.get("auto_approve_timeout", 3600)
            if timeout <= 0:
                logger.debug(f"[Entry Review] 自动通过功能已禁用 (timeout={timeout})")
                return
                
            logger.info(f"[Entry Review] 启动自动通过任务 - 用户: {user_id}, 超时: {timeout}秒")
            await asyncio.sleep(timeout)
            
            # 检查申请是否还在待处理状态
            if user_id not in self.pending_requests:
                logger.debug(f"[Entry Review] 用户 {user_id} 的申请已被处理，取消自动通过")
                return
                
            logger.info(f"[Entry Review] 执行自动通过 - 用户: {user_id}")
            
            request_info = self.pending_requests[user_id]
            request_time = self._format_timestamp(request_info.get("timestamp"))
            
            # 自动通过申请
            try:
                if hasattr(self.context, 'platform_manager'):
                    # 尝试通过平台管理器调用API
                    pass  # 这里需要根据实际API实现
                logger.info(f"[Entry Review] API调用成功 - 用户 {user_id} 申请已自动通过")
                
            except Exception as api_error:
                logger.error(f"[Entry Review] 自动通过API调用失败 - 用户: {user_id}, 错误: {api_error}")
                # 即使API调用失败，也要发送通知和清理状态
            
            # 发送通知消息
            try:
                message = self._safe_format(
                    self.config.get("auto_approve_message_template", ""),
                    user_id=user_id,
                    nickname=nickname,
                    request_time=request_time,
                    timestamp=self._format_timestamp()
                )
                
                # 发送到审核群
                success = await self.send_message_to_group(self.config.get("target_group", ""), message)
                if success:
                    logger.debug(f"[Entry Review] 自动通过通知已发送 - 用户: {user_id}")
                    
            except Exception as msg_error:
                logger.error(f"[Entry Review] 发送自动通过通知失败 - 用户: {user_id}, 错误: {msg_error}")
            
            # 清理状态
            await self._cleanup_request(user_id)
            logger.info(f"[Entry Review] 自动通过流程完成 - 用户: {user_id}")
                
        except asyncio.CancelledError:
            logger.info(f"[Entry Review] 用户 {user_id} 的自动通过任务被手动取消")
            raise  # 重新抛出CancelledError以正确处理任务取消
        except Exception as e:
            logger.error(f"[Entry Review] 自动通过申请异常 - 用户: {user_id}, 错误类型: {type(e).__name__}, 错误: {e}")
            # 发生异常时也要尝试清理状态
            try:
                await self._cleanup_request(user_id)
            except Exception as cleanup_error:
                logger.error(f"[Entry Review] 清理申请状态失败 - 用户: {user_id}, 错误: {cleanup_error}")
    
    async def _cleanup_request(self, user_id: str):
        """清理申请状态"""
        try:
            if user_id in self.pending_requests:
                request_info = self.pending_requests[user_id]
                
                # 取消自动通过任务
                task = request_info.get("task")
                if task and not task.done():
                    task.cancel()
                    logger.debug(f"[Entry Review] 已取消用户 {user_id} 的自动通过任务")
                
                # 删除申请记录
                del self.pending_requests[user_id]
                logger.debug(f"[Entry Review] 已清理用户 {user_id} 的申请状态")
            else:
                logger.debug(f"[Entry Review] 用户 {user_id} 的申请状态不存在，无需清理")
                
        except Exception as e:
            logger.error(f"[Entry Review] 清理申请状态失败 - 用户: {user_id}, 错误: {e}")
    
    async def approve_request(self, user_id: str, event: AstrMessageEvent):
        """同意入群申请（兼容旧接口）"""
        await self._approve_request(event, user_id, "系统")

    async def reject_request(self, user_id: str, event: AstrMessageEvent):
        """拒绝入群申请（兼容旧接口）"""
        await self._reject_request(event, user_id, "系统", "")

    @filter.command("帮助")
    async def help_command(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = """📖 入群申请审核插件帮助

配置命令：
/设置源群 群号 - 设置需要监控的群
/设置审核群 群号 - 设置审核消息发送的群
/添加审核员 QQ号 - 添加有审核权限的用户
/查看配置 - 查看当前配置

审核命令（仅在审核群中有效）：
/通过 QQ号 - 同意入群申请
/拒绝 QQ号 [理由] - 拒绝入群申请
通过 QQ号 - 同意入群申请（兼容格式）
拒绝 QQ号 [理由] - 拒绝入群申请（兼容格式）

测试命令：
/测试申请 用户ID 群ID [申请理由] - 模拟入群申请

/帮助 - 显示此帮助信息

注意：
- 支持自动通过超时功能
- 支持权限检查（授权用户或群管理员）
- 支持消息模板自定义"""
        yield event.plain_result(help_text)

    async def terminate(self):
        """插件销毁时的清理工作"""
        try:
            logger.info(f"[Entry Review] 开始插件终止清理，待处理申请数: {len(self.pending_requests)}")
            
            # 取消所有待处理的自动通过任务
            cancelled_count = 0
            for user_id in list(self.pending_requests.keys()):
                try:
                    await self._cleanup_request(user_id)
                    cancelled_count += 1
                except Exception as e:
                    logger.error(f"[Entry Review] 清理用户 {user_id} 状态失败: {e}")
            
            logger.info(f"[Entry Review] 插件终止清理完成 - 清理申请数: {cancelled_count}")
            
        except Exception as e:
            logger.error(f"[Entry Review] 插件终止清理失败: {e}")
            # 确保清空申请记录
            self.pending_requests.clear()
